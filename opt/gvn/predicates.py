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
            rep = a if isinstance(a.op, int) else b
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

