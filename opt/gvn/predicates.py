"""
Predicates
============
Goldthorpe

This module provides data structures for managing predicates on abstract
expressions.
"""

from utils.syntax import Syntax

from opt.gvn.expr import Expr

import ampy.types as amt

class Comparisons:
    """
    Data structure for a conjunction of several inequality and unequality
    assertions.
    Values are stored in a DAG, where nodes represent equality classes, and
    there is an edge from a to b iff a <= b.
    """
    # This version should be more efficient than the last (and also
    # more correct). Appending a chain %0 <= %1 <= ... <= %n should take O(n log n)
    # time because of the lheight and rheight dicts.
    # however, afterward asserting a chain of assertions k <= %(n-k) for increasing k
    # is likely O(n^2) because of update propagation (but I doubt this kind of thing
    # would happen much in practice... I can't believe I said that).

    def __init__(self):
        self._eq = {} # union-find dict for equality classes
        self._leq = {} # DAG of inequalities (a in leq[b] iff a <= b)
        self._geq = {} # a in geq[b] iff a >= b
        self._neq = {} # unequality assertions
        self._int_range = {} # int_range[a] = [lo, hi] interval
        self._lheight = {} # approximation for longest chain to the left
        self._rheight = {} # approximation for longest chain to the right
        self._consistent = True

    def copy(self):
        """
        Create a separate Comparisons object with identical data
        (deep copy)
        """
        ret = Comparisons()
        if not self._consistent:
            ret._consistent = False
            return ret
        for node in self:
            ret._eq[node] = self._eq[node]
            if self._eq[node] == node:
                ret._neq[node] = set(self._neq[node])
                ret._leq[node] = set(self._leq[node])
                ret._geq[node] = set(self._geq[node])
                ret._int_range[node] = self._int_range[node]
                ret._lheight[node] = self._lheight[node]
                ret._rheight[node] = self._rheight[node]
        return ret


    @(Syntax(object, Expr) >> bool)
    def __in__(self, node):
        return node in self._eq
    
    @(Syntax(object) >> [iter, Expr])
    def __iter__(self):
        for node in self._eq:
            yield node

    @(Syntax(object) >> bool)
    def is_consistent(self):
        if not self._consistent:
            return False
        for node in self:
            self.eqclass(node) # force path compression
        return self._consistent

    @(Syntax(object, Expr) >> None)
    def add(self, node):
        if not self._consistent:
            return
        if node not in self:
            self._eq[node] = node
            self._leq[node] = {node}
            self._geq[node] = {node}
            self._neq[node] = set()
            self._lheight[node] = 0
            self._rheight[node] = 0
            if isinstance(node.op, int):
                self._int_range[node] = (node.op, node.op)
            elif isinstance(node.op, type) and issubclass(node.op, amt.CompInstructionClass):
                self._int_range[node] = (0, 1) # False / True
            else:
                self._int_range[node] = (None, None)

    @(Syntax(object, Expr) >> Expr)
    def eqclass(self, node):
        if not self._consistent:
            return node
        if node not in self:
            self.add(node)
        if isinstance(node.op, int):
            return node

        # union-find
        head = self._eq[node]
        if (top := self._eq[head]) != head:
            top = self.eqclass(head)
            self._update_eq(head, top)
            self._update_eq(node, top) # path compression
            head = top

        return head
    
    @(Syntax(object, Expr, Expr) >> None)
    def assert_leq(self, a, b):
        if not self._consistent:
            return
        a = self.eqclass(a)
        b = self.eqclass(b)

        if self.leq(b, a):
            # they now form an equivalence class
            rep = min(a, b) # expressions have a canonical order (with consts as mins)
            self._update_eqclass(a, b, rep)
        else:
            self._update_leq(a, b)

    @(Syntax(object, Expr, Expr) >> None)
    def assert_eq(self, a, b):
        if not self._consistent:
            return
        self.assert_leq(a, b)
        self.assert_leq(b, a)

    @(Syntax(object, Expr, Expr) >> None)
    def assert_neq(self, a, b):
        if not self._consistent:
            return
        a = self.eqclass(a)
        b = self.eqclass(b)
        if a == b:
            self._consistent = False
            return
        self._neq[a].add(b)
        self._neq[b].add(a)
        if self.leq(a, b):
            lo, _ = self._int_range[a]
            _, hi = self._int_range[b]
            if lo is not None:
                self._update_int_range(b, lo+1, None)
            if hi is not None:
                self._update_int_range(a, None, hi-1)
        if self.leq(b, a):
            lo, _ = self._int_range[b]
            _, hi = self._int_range[a]
            if lo is not None:
                self._update_int_range(a, lo+1, None)
            if hi is not None:
                self._update_int_range(b, None, hi-1)

    @(Syntax(object, Expr, Expr, _fast=bool) >> bool)
    def leq(self, a, b, *, _fast=True):
        """
        Indicate if a is provably less than b
        """
        if not self._consistent:
            return False
        a = self.eqclass(a)
        b = self.eqclass(b)
        seen = set()
        def less(lhs, rhs):
            if lhs == rhs:
                return True
            seen.add((lhs, rhs))
            if _fast and rhs in self._leq[lhs]:
                return False
            llo, lhi = self._int_range[lhs]
            rlo, rhi = self._int_range[rhs]
            res = False
            if lhi is not None and rlo is not None and lhi <= rlo:
                res = True
            elif llo is not None and rhi is not None and llo > rhi:
                self._update_leq(rhs, lhs)
            else:
                if self._rheight[lhs] > self._lheight[rhs]:
                    # traverse left
                    for lt in list(self._leq[rhs]):
                        lt = self.eqclass(lt)
                        if (lhs,lt) not in seen and less(lhs, lt):
                            res = True
                            break
                else:
                    # traverse right
                    for gt in list(self._geq[lhs]):
                        gt = self.eqclass(gt)
                        if (gt, rhs) not in seen and less(gt, rhs):
                            res = True
                            break
            if res:
                self._update_leq(lhs, rhs)
                return True
            return False

        return less(a, b)

    @(Syntax(object, Expr, Expr) >> bool)
    def eq(self, a, b):
        """
        Indicate if a is provably equal to b
        """
        a = self.eqclass(a)
        b = self.eqclass(b)
        return a == b

    @(Syntax(object, Expr, Expr) >> bool)
    def neq(self, a, b):
        """
        Indicate if a is provably unequal to b
        """
        if not self._consistent:
            return False
        a = self.eqclass(a)
        b = self.eqclass(b)
        if a in self._neq[b]:
            return True
        alo, ahi = self._int_range[a]
        blo, bhi = self._int_range[b]
        if alo is not None and bhi is not None and alo > bhi:
            self._update_leq(b, a)
            self.assert_neq(a, b)
            return True
        if ahi is not None and blo is not None and blo > ahi:
            self._update_leq(a, b)
            self.assert_neq(a, b)
            return True
        return False

    @(Syntax(object, Expr) >> ((), (int, None), (int, None)))
    def int_range(self, expr):
        """
        Give the integer range of an expression, if known
        """
        expr = self.eqclass(expr)
        return self._int_range[expr]
    
    @(Syntax(object, Expr, Expr) >> None)
    def _update_eq(self, node, head):
        if self._eq[node] == head:
            return
        if node not in self._leq:
            return
        self._eq[node] = head
        lo, hi = self._int_range.pop(node)
        self._update_int_range(head, lo, hi)
        self._lheight[head] = max(self._lheight[head], self._lheight.pop(node))
        self._rheight[head] = max(self._rheight[head], self._rheight.pop(node))
        for lt in self._leq.pop(node):
            lt = self.eqclass(lt)
            if lt not in self._leq[head]:
                self._update_leq(lt, head)
        for gt in self._geq.pop(node):
            gt = self.eqclass(gt)
            if gt not in self._geq[head]:
                self._update_leq(head, gt)
        for neq in self._neq.pop(node):
            self._neq[neq].remove(node)
            self.assert_neq(head, neq)

    @(Syntax(object, Expr, (int, None), (int, None)) >> None)
    def _update_int_range(self, node, newlo, newhi):
        if not self._consistent:
            return
        node = self.eqclass(node)
        old = self._int_range[node]
        lo, hi = old
        if newlo is not None:
            lo = newlo if lo is None or lo < newlo else lo
        if newhi is not None:
            hi = newhi if hi is None or hi > newhi else hi
        
        neq = self._neq[node]

        if lo is not None:
            while Expr(lo) in neq:
                lo += 1
        if hi is not None:
            while Expr(hi) in neq:
                hi -= 1

        if lo is not None and hi is not None:
            if lo > hi:
                self._consistent = False
                return

        self._int_range[node] = (lo, hi)
        leq = list(self._leq[node])
        geq = list(self._geq[node])

        if lo != old[0]: # implies lo is not None
            for gt in geq:
                gt = self.eqclass(gt)
                glo = self._int_range[gt][0]
                nglo = lo + self.neq(node, gt)
                if glo is None or glo < nglo:
                    self._update_int_range(gt, nglo, None)
        if hi != old[1]:
            for lt in leq:
                lt = self.eqclass(lt)
                lhi = self._int_range[lt][1]
                nlhi = hi - self.neq(node, lt)
                if lhi is None or lhi > nlhi:
                    self._update_int_range(lt, None, nlhi)

        if lo is not None and hi is not None:
            if lo == hi:
                self._update_eq(node, Expr(lo))

    @(Syntax(object, Expr, Expr) >> None)
    def _update_leq(self, a, b):
        if not self._consistent:
            return
        if a in self._leq[b]:
            return
        self._leq[b].add(a)
        self._geq[a].add(b)
        self._lheight[b] = max(self._lheight[b], self._lheight[a]+1)
        self._rheight[a] = max(self._rheight[a], self._rheight[b]+1)
        lo, _ = self._int_range[a]
        _, hi = self._int_range[b]
        if lo is not None:
            self._update_int_range(b, lo+self.neq(a, b), None)
        if hi is not None:
            self._update_int_range(a, None, hi-self.neq(a, b))
    
    @(Syntax(object, Expr, Expr, Expr) >> None)
    def _update_eqclass(self, node, bot, rep):
        """
        Set the eqclass rep for node to rep so long as node >= bot
        """
        if not self._consistent:
            return
        seen = set()
        to_process = {node}
        cls = set()
        while len(to_process) > 0:
            n = to_process.pop()
            seen.add(n)
            if self.leq(bot, n):
                cls.add(n)
                if n in self._leq:
                    for lt in self._leq[n]:
                        if lt in seen:
                            continue
                        to_process.add(lt)

        for n in cls:
            self._update_eq(n, rep)

class PredicatedState:
    """
    Data structure for managing simple predicated expression
    simplification.
    """

    def __init__(self):
        self._comparisons = Comparisons()

    def copy(self):
        ret = PredicatedState()
        ret._comparisons = self._comparisons.copy()
        return ret

    @(Syntax(object, [set, Expr]) >> Expr)
    def expr(self, exprs):
        """
        Summarises all relations between elements of `expr_set` as a large
        conjunction
        """
        if not self.consistent:
            return Expr(0)

        conj = []
        exprs = list(filter(lambda e: not isinstance(e.op, int), exprs))
        for lhs in exprs:
            lo, hi = self._comparisons.int_range(lhs)
            if lo == hi:
                if lo is not None:
                    conj.append(Expr(amt.EqInstruction, Expr(lo), lhs))
            else:
                if lo is not None:
                    conj.append(Expr(amt.LeqInstruction, Expr(lo), lhs))
                if hi is not None:
                    conj.append(Expr(amt.LeqInstruction, lhs, Expr(hi)))
            for rhs in exprs:
                if self._comparisons.eq(lhs, rhs):
                    conj.append(Expr(amt.EqInstruction, lhs, rhs))
                else:
                    if self._comparisons.leq(lhs, rhs):
                        conj.append(Expr(amt.LeqInstruction, lhs, rhs))
                    if self._comparisons.neq(lhs, rhs):
                        conj.append(Expr(amt.NeqInstruction, lhs, rhs))
        return Expr(amt.AndInstruction, *filter(lambda e: not isinstance(e.op, int), conj))
    

    @property
    def consistent(self):
        return self._comparisons.is_consistent()

    @(Syntax(object, Expr) >> Expr)
    def simplify(self, expr):
        """
        Attempt to simplify an expression with the information provided
        by predicates.
        """
        # e.g. if expression is given by a comparison, then its value is bounded between 0 and 1
        # or if it is a division/mod, then its second argument is nonzero
        # first, simplify its arguments
        expr = Expr(expr.op, *map(self.simplify, expr.args))
        # then take the "representative" for the expression
        expr = self._comparisons.eqclass(expr)

        match expr.op:

            case amt.AddInstruction:
                if len(expr.args) == 2:
                    # otherwise, expressions are too complicated
                    nleft = Expr(amt.MulInstruction, Expr(-1), expr.left)
                    if self._comparisons.leq(expr.right, nleft):
                        self._comparisons.assert_leq(expr, Expr(0))
                    if self._comparisons.leq(nleft, expr.right):
                        self._comparisons.assert_leq(Expr(0), expr)
                    if self._comparisons.leq(Expr(0), expr.left):
                        self._comparisons.assert_leq(expr.right, expr)
                    if self._comparisons.leq(expr.left, Expr(0)):
                        self._comparisons.assert_leq(expr, expr.right)
                    if self._comparisons.leq(Expr(0), expr.right):
                        self._comparisons.assert_leq(expr.left, expr)
                    if self._comparisons.leq(expr.right, Expr(0)):
                        self._comparisons.assert_leq(expr, expr.left)

            case amt.MulInstruction:
                positives = len(list(filter(lambda arg: self._comparisons.leq(Expr(0), arg), expr.args)))
                negatives = len(list(filter(lambda arg: self._comparisons.leq(arg, Expr(0)), expr.args)))
                if positives + negatives == len(expr.args):
                    if negatives % 2 == 0:
                        self._comparisons.assert_leq(Expr(0), expr)
                    else:
                        self._comparisons.assert_leq(expr, Expr(0))

            case amt.ModInstruction:
                nleft = Expr(amt.MulInstruction, Expr(-1), expr.left)
                if self._comparisons.leq(Expr(0), expr.right):
                    # by convention a % b is nonnegative iff b is
                    self._comparisons.assert_leq(Expr(0), expr)
                    if self._comparisons.leq(Expr(0), expr.left):
                        if self._comparisons.leq(expr.left, expr.right):
                            # a % b = a if 0 <= a < b
                            self._comparisons.assert_eq(expr, expr.left)
                    elif self._comparisons.leq(Expr(0), nleft):
                        if self._comparisons.leq(nleft, expr.right):
                            self._comparisons.assert_eq(expr, Expr(amt.AddInstruction, expr.right, expr.left))
                elif self._comparisons.leq(expr.right, Expr(0)):
                    self._comparisons.assert_leq(expr, Expr(0))
                    if self._comparisons.leq(expr.left, Expr(0)):
                        if self._comparisons.leq(expr.right, expr.left):
                            # a % b = a if b < a <= 0
                            self._comparisons.assert_eq(expr, expr.left)
                    elif self._comparisons.leq(nleft, Expr(0)):
                        if self._comparisons.leq(expr.right, nleft):
                            self._comparisons.assert_eq(expr, Expr(amt.AddInstruction, expr.left, expr.right))

            case amt.DivInstruction:
                # because of expr simplifications, we already know
                # that a != b and a,b != 0
                nleft = Expr(amt.MulInstruction, Expr(-1), expr.left)
                if self._comparisons.eq(nleft, expr.right):
                    self._comparisons.assert_eq(expr, Expr(-1))
                if self._comparisons.leq(Expr(0), expr.right):
                    if self._comparisons.leq(Expr(0), expr.left):
                        self._comparisons.assert_leq(Expr(0), expr)
                        if self._comparisons.leq(expr.left, expr.right):
                            # 0 <= a < b, so a / b = 0
                            self._comparisons.assert_eq(Expr(0), expr)
                    elif self._comparisons.leq(Expr(0), nleft):
                        self._comparisons.assert_leq(expr, Expr(0))
                        if self._comparisons.leq(nleft, expr.right):
                            self._comparisons.assert_eq(Expr(0), expr)
                elif self._comparisons.leq(expr.right, Expr(0)):
                    # opposite of above work
                    if self._comparisons.leq(expr.left, Expr(0)):
                        self._comparisons.assert_leq(Expr(0), expr)
                        if self._comparisons.leq(expr.right, expr.left):
                            self._comparisons.assert_eq(Expr(0), expr)
                    elif self._comparisons.leq(nleft, Expr(0)):
                        self._comparisons.assert_leq(expr, Expr(0))
                        if self._comparisons.leq(expr.right, nleft):
                            self._comparisons.assert_eq(Expr(0), expr)

            case amt.AndInstruction:
                # a & b is positive unless both a and b are negative
                if any(self._comparisons.leq(Expr(0), arg) for arg in expr.args):
                    self._comparisons.assert_leq(Expr(0), expr)
                elif all(self._comparisons.leq(arg, Expr(0)) for arg in expr.args):
                    self._comparisons.assert_leq(expr, Expr(0))

            case amt.OrInstruction:
                # a | b is negative unless both a and b are positive
                if any(self._comparisons.leq(arg, Expr(0)) for arg in expr.args):
                    self._comparisons.assert_leq(expr, Expr(0))
                elif all(self._comparisons.leq(Expr(0), arg) for arg in expr.args):
                    self._comparisons.assert_leq(Expr(0), expr)

            case amt.XOrInstruction:
                if len(expr.args) == 2:
                    # otherwise, it's too complicated
                    if self._comparisons.neq(expr.left, expr.right):
                        # we know the arguments are not provably equal already
                        self._comparisons.assert_neq(expr, Expr(0))

            case amt.LShiftInstruction | amt.RShiftInstruction:
                if self._comparisons.leq(Expr(0), expr.left):
                    self._comparisons.assert_leq(Expr(0), expr)
                elif self._comparisons.leq(expr.left, Expr(0)):
                    self._comparisons.assert_leq(expr, Expr(0))

            case T if isinstance(T, type) and issubclass(T, amt.CompInstructionClass):
                self._comparisons.assert_leq(expr, Expr(1))
                self._comparisons.assert_leq(Expr(0), expr)

                right, left = self.split_subtraction(expr.right)
                # 0 < [B] - [A] iff [A] < [B], so left = [A], right = [B]

                match T:
                    case amt.EqInstruction:
                        if self._comparisons.neq(left, right):
                            self._comparisons.assert_eq(expr, Expr(0))
                    case amt.NeqInstruction:
                        if self._comparisons.neq(left, right):
                            self._comparisons.assert_eq(expr, Expr(1))
                    case amt.LeqInstruction:
                        if self._comparisons.leq(left, right):
                            self._comparisons.assert_eq(expr, Expr(1))
                        elif self._comparisons.leq(right, left) and self._comparisons.neq(right, left):
                            self._comparisons.assert_eq(expr, Expr(0))
                    case amt.LtInstruction:
                        if self._comparisons.eq(left, right):
                            self._comparisons.assert_eq(expr, Expr(0))
                        elif self._comparisons.neq(left, right):
                            if self._comparisons.leq(left, right):
                                self._comparisons.assert_eq(expr, Expr(1))
                            elif self._comparisons.leq(right, left):
                                self._comparisons.assert_eq(expr, Expr(0))

            case _:
                # the following do not have any nontrivial simplifications
                # (that aren't already done automatically at this point)
                # consts
                # phis
                pass

        return self._comparisons.eqclass(expr)
    
    @classmethod
    @(Syntax(object, Expr) >> ((), Expr, Expr))
    def split_subtraction(cls, expr):
        """
        Try to split the expression into [A] - [B]
        and return (A, B)
        """
        if expr.op != amt.AddInstruction:
            return (expr, Expr(0))
        def negated(e):
            return e.op == amt.MulInstruction and e.left.op == -1
        negs = Expr(amt.AddInstruction, *map(lambda e: e.right, filter(negated, expr.args)))
        if negs.op == 0:
            # no "negatives"
            return (Expr(amt.AddInstruction, *expr.args[1:]),
                    Expr(amt.MulInstruction, Expr(-1), expr.left))
        return (Expr(amt.AddInstruction, *filter(lambda e: not negated(e), expr.args)), negs)

    @(Syntax(object, Expr) >> None)
    def assert_nonzero(self, expr):
        """
        Try to infer elementary consequences from the fact
        that the provided expression is nonzero.

        Assumes variables in expr are atomic; for instance,
        if (a == 0) is asserted, and (a == b - c) is already
        known, this will not infer that (b == c).
        To do this, assert that (b - c == 0) is nonzero instead.
        """
        expr = Expr(expr.op, *map(self.simplify, expr.args))
        match expr.op:

            case T if isinstance(T, int):
                if T == 0:
                    # contradiction
                    self._comparisons._consistent = False
                # either way, nothing to infer
            
            case T if isinstance(T, str):
                self._comparisons.assert_neq(expr, Expr(0))

            case amt.AddInstruction:
                # a + b != 0 iff a != -b
                #TODO: do you want exponentially many inferences?
                if len(expr.args) > 2:
                    # do nothing; too many cases
                    self._comparisons.assert_neq(expr, Expr(0))
                else:
                    self._comparisons.assert_neq(expr.left,
                            Expr(amt.MulInstruction, Expr(-1), expr.right))
                    self._comparisons.assert_neq(expr.right,
                            Expr(amt.MulInstruction, Expr(-1), expr.left))

            case amt.MulInstruction:
                # a * b != 0 iff a != 0 and b != 0
                for arg in expr.args:
                    self.assert_nonzero(arg)

            case amt.DivInstruction:
                # a / b != 0 iff a != 0 and b != 0
                self.assert_nonzero(expr.left)
                self.assert_nonzero(expr.right)

            case amt.ModInstruction:
                # a % b != 0 implies a != b, b != 0, and a != 0
                self.assert_nonzero(Expr(amt.EqInstruction,
                    expr.left, expr.right))
                self.assert_nonzero(expr.left)
                self.assert_nonzero(expr.right)
                self._comparisons.assert_neq(expr, Expr(0))

            case amt.AndInstruction:
                # a & b != 0 iff a != 0 and b != 0
                for arg in expr.args:
                    self.assert_nonzero(arg)
            
            case amt.XOrInstruction:
                # a ^ b != 0 iff a != b
                if len(expr.args) > 2:
                    # too many to handle
                    self._comparisons.assert_neq(expr, Expr(0))
                else:
                    self.assert_nonzero(Expr(amt.NeqInstruction, expr.left, expr.right))

            case amt.EqInstruction:
                # (0 == a) != 0 iff a == 0
                # recall that canonical form puts 0 on the left
                self.assert_zero(expr.right)
                self.assert_zero(Expr(amt.MulInstruction, Expr(-1), expr.right))

            case amt.NeqInstruction:
                # (0 != a) != 0 iff a != 0
                self.assert_nonzero(expr.right)
                self.assert_nonzero(Expr(amt.MulInstruction, Expr(-1), expr.right))

            case amt.LeqInstruction | amt.LtInstruction:
                # (0 <= a - b) != 0 iff b <= a iff -b >= -a
                lhs, rhs = self.split_subtraction(expr.right)
                self._comparisons.assert_leq(rhs, lhs)
                if expr.op == amt.LtInstruction:
                    self._comparisons.assert_neq(lhs, rhs)
                lhs, rhs = map(lambda e: Expr(amt.MulInstruction, Expr(-1), e), (lhs, rhs))
                self._comparisons.assert_leq(lhs, rhs)
                if expr.op == amt.LtInstruction:
                    self._comparisons.assert_neq(lhs, rhs)

            case _:
                # phi instructions
                # or  instructions
                # lsh instructions
                # rsh instructions
                # nothing nontrivial to infer
                self._comparisons.assert_neq(expr, Expr(0))

    @(Syntax(object, Expr) >> None)
    def assert_zero(self, expr):
        """
        Try to infer elementary consequences from the fact
        that the provided expression is zero.
        """
        expr = Expr(expr.op, *map(self.simplify, expr.args))
        match expr.op:

            case T if isinstance(T, int):
                if T != 0:
                    # contradiction
                    self._comparisons._consistent = False
                # otherwise, nothing to infer

            case T if isinstance(T, str):
                self._comparisons.assert_eq(expr, Expr(0))

            case amt.AddInstruction:
                # a + b == 0 iff a == -b
                #TODO: do you want exponentially many inferences?
                if len(expr.args) > 2:
                    # do nothing; too many cases
                    self._comparisons.assert_eq(expr, Expr(0))
                else:
                    self._comparisons.assert_eq(expr.left,
                            Expr(amt.MulInstruction, Expr(-1), expr.right))
                    self._comparisons.assert_eq(expr.right,
                            Expr(amt.MulInstruction, Expr(-1), expr.left))

            case amt.DivInstruction:
                # a / b == 0 iff a == 0
                self.assert_zero(expr.left)

            case amt.OrInstruction:
                # a | b == 0 iff a == 0 and b == 0
                for arg in expr.args:
                    self.assert_zero(arg)

            case amt.XOrInstruction:
                # a ^ b == 0 iff a == b
                if len(expr.args) > 2:
                    # too many to handle
                    self._comparisons.assert_eq(expr, Expr(0))
                else:
                    self.assert_nonzero(Expr(amt.EqInstruction, expr.left, expr.right))

            case amt.EqInstruction:
                # (0 == a) == 0 iff a != 0
                # recall that canonical form puts 0 on the left
                self.assert_nonzero(expr.right)

            case amt.NeqInstruction:
                # (0 != a) == 0 iff a == 0
                self.assert_zero(expr.right)

            case amt.LeqInstruction | amt.LtInstruction:
                # (0 <= a - b) == 0 iff a < b iff -a > -b
                lhs, rhs = self.split_subtraction(expr.right)
                self._comparisons.assert_leq(lhs, rhs)
                if expr.op == amt.LeqInstruction:
                    self._comparisons.assert_neq(lhs, rhs)
                lhs, rhs = map(lambda e: Expr(amt.MulInstruction, Expr(-1), e), (lhs, rhs))
                self._comparisons.assert_leq(rhs, lhs)
                if expr.op == amt.LeqInstruction:
                    self._comparisons.assert_neq(lhs, rhs)

            case _:
                # phi instructions
                # mul instructions
                # mod instructions
                # and instructions
                # lsh instructions
                # rsh instructions
                # nothing nontrivial to infer
                self._comparisons.assert_eq(expr, Expr(0))
