"""
Abstract expressions
======================
Goldthorpe

This module provides a datatype for managing abstract computation expressions,
primarily for value numbering.
"""

from utils.syntax import Syntax, Assertion
from opt.tools import OptError

import ampy.types as amt

class Expr:
    # forward declaration
    pass

class Expr(Expr):
    """
    Formal computational expression, with rewriting rules
    """
    @(Syntax(object, int, reduce=bool)
      | Syntax(object, str, reduce=bool)
      | Syntax(object, ((type, Assertion(lambda T: issubclass(T, amt.DefInstructionClass))),), Expr, ..., reduce=bool))
    def __init__(self, op, *exprs, reduce=True):
        # an expression is an AST whose leaf nodes are constants / registers
        #
        # op: operation or constant
        # args: arguments
        self.op = op
        self.args = list(exprs)
        if reduce:
            self.reduce()

    ### convenient getters/setters ###

    @property
    @(Syntax(object) >> Expr)
    def left(self):
        return self.args[0]
    @left.setter
    @(Syntax(object, Expr) >> None)
    def left(self, expr):
        self.args[0] = expr

    @property
    @(Syntax(object) >> Expr)
    def right(self):
        return self.args[-1]
    @right.setter
    @(Syntax(object, Expr) >> None)
    def right(self, expr):
        self.args[-1] = expr

    ### for printing ###
    
    def __str__(self):

        if isinstance(self.op, (int, str)):
            rep = str(self.op)
            if rep.startswith('-'):
                return f"({rep})"
            return rep

        if issubclass(self.op, amt.BinaryInstructionClass):
            return "({})".format(f" {self.op.op} ".join(str(arg) for arg in self.args))

        if self.op == amt.PhiInstruction:
            return "phi({})".format("; ".join(
                "{}, {}".format(str(self.args[2*i]), str(self.args[2*i+1]))
                for i in range(len(self.args)//2)))

        # new definition instruction
        return f"{self.op}({', '.join(str(arg) for arg in self.args)})"

    def __repr__(self):
        return f"Expr<{self}>"

    ### for metadata ###

    @property
    @(Syntax(object) >> str)
    def polish(self):
        """
        Convert expression into Polish notation.
        All operations come with a specified arity as "op`arity"
        """
        if isinstance(self.op, (int, str)):
            return f"{self.op}"
        if issubclass(self.op, amt.BinaryInstructionClass):
            op = self.op.op
        elif self.op == amt.PhiInstruction:
            op = "phi"
        else: # should not be possible
            op = "?"
        return f"{op}`{len(self.args)} " + ' '.join(arg.polish for arg in self.args)

    @classmethod
    @(Syntax(object, str) >> Expr)
    def read_polish(cls, polish):
        """
        Parse Polish notation
        """
        return cls.read_polish_ls(polish.split(), 0)[0]

    @classmethod
    @(Syntax(object, [str], int) >> ((), Expr, int))
    def read_polish_ls(cls, polish, i):
        """
        Given the Polish expr as a list of terms, and a starting index i,
        returns a pair (expr, j), where expr is the expression obtained by
        parsing the terms in the interval [i, j).
        """
        if '`' not in polish[i]:
            return Expr(polish[i]), i+1

        op, arity = polish[i].split('`', 1)
        arity = int(arity)

        # collect all arguments
        args = []
        j = i+1
        for _ in range(arity):
            expr, j = Expr.read_polish_ls(polish, j)
            args.append(expr)

        match op:
            case '+':
                return Expr(amt.AddInstruction, *args), j
            case '-':
                return Expr(amt.SubInstruction, *args), j
            case '*':
                return Expr(amt.MulInstruction, *args), j
            case '/':
                return Expr(amt.DivInstruction, *args), j
            case '%':
                return Expr(amt.ModInstruction, *args), j
            case '&':
                return Expr(amt.AndInstruction, *args), j
            case '|':
                return Expr(amt.OrInstruction, *args), j
            case '^':
                return Expr(amt.XOrInstruction, *args), j
            case "<<":
                return Expr(amt.LShiftInstruction, *args), j
            case ">>":
                return Expr(amt.RShiftInstruction, *args), j
            case "==":
                return Expr(amt.EqInstruction, *args), j
            case "!=":
                return Expr(amt.NeqInstruction, *args), j
            case '<':
                return Expr(amt.LtInstruction, *args), j
            case "<=":
                return Expr(amt.LeqInstruction, *args), j
            case "phi":
                return Expr(amt.PhiInstruction, *args), j
            case T:
                # shouldn't happen
                raise NotImplementedError(f"Unrecognised operand {T} of arity {arity}.")


    ### comparisons ###
    @(Syntax(object, Expr) >> int)
    def compare(self, other):
        """
        Returns -1, 0, 1 if self is lt, eq, gt other (respectively).
        Total ordering is somewhat arbitrary:
        integers < registers
        expressions with matching operations are sorted by arity
        then sorted in lexicographical order by arguments
        """
        def cmp(a, b):
            return (a > b) - (a < b)
        if self.op == other.op:
            if isinstance(self.op, (int, str)):
                return 0
            if (res := cmp(len(self.args), len(other.args))) != 0:
                return res
            for L, R in zip(self.args, other.args):
                if (res := L.compare(R)) != 0:
                    return res
            return 0

        if isinstance(self.op, int):
            if isinstance(other.op, int):
                return cmp(self.op, other.op)
            return -1
        if isinstance(other.op, int):
            return +1
        if isinstance(self.op, str):
            if isinstance(other.op, str):
                return cmp(self.op, other.op)
            return -1
        if isinstance(other.op, str):
            return +1

        order = (
                amt.AddInstruction,
                amt.SubInstruction,
                amt.MulInstruction,
                amt.DivInstruction,
                amt.ModInstruction,
                amt.AndInstruction,
                amt.OrInstruction,
                amt.XOrInstruction,
                amt.LShiftInstruction,
                amt.RShiftInstruction,
                amt.EqInstruction,
                amt.NeqInstruction,
                amt.LtInstruction,
                amt.LeqInstruction,
                amt.PhiInstruction,
                )

        for op in order:
            if self.op == op:
                return -1
            if other.op == op:
                return +1

        # we should not be able to reach here
        raise NotImplementedError

    @(Syntax(object, Expr) >> bool)
    def __eq__(self, other):
        return self.compare(other) == 0

    @(Syntax(object, Expr) >> bool)
    def __ne__(self, other):
        return self.compare(other) != 0

    @(Syntax(object, Expr) >> bool)
    def __lt__(self, other):
        return self.compare(other) == -1

    @(Syntax(object, Expr) >> bool)
    def __le__(self, other):
        return self.compare(other) <= 0

    def __hash__(self):
        #TODO: don't hash; this data structure is inefficient to
        # hash and then check equality with
        return hash((self.op, tuple(self.args)))

    ### rewriting ###
    @(Syntax(object) >> None)
    def reduce(self):
        """
        Apply rewriting rules to put expression into a canonical form.
        The hope is that two expressions are equivalent precisely if
        their canonical forms coincide, but this will only be an approximation
        since I am not thinking through all possible rewriting rules.

        The assumption is that the operands are already reduced.
        """
        # rewriting rules implemented:
        # redundancy: a - b = a + (-1)*b
        # associativity: +, *, &, |, ^
        # commutativity: +, *, &, |, ^
        # c-distributivity: (*,+) (&,|^)
        #    (we do not distribute (|,&) as this would cause infinite recursion)
        # l-distrivutivity: (<<,+&|^), (>>,&|^)
        # exponent rules for << and >>

        if isinstance(self.op, (int, str)):
            return

        while True:

            match self.op:

                case amt.PhiInstruction:
                    # not much we can do with these
                    # besides group its operands by label and hope things align
                    #TODO: uses hashing
                    mapping = {}
                    for i in range(len(self.args)//2):
                        val = self.args[2*i]
                        label = self.args[2*i+1]
                        mapping.setdefault(val, set()).add(label)
                    if len(mapping) == 1:
                        # phi is actually just a copy
                        new, _ = mapping.popitem()
                        self.op = new.op
                        self.args = new.args
                        return
                    self.args = []
                    for val, labelset in sorted(mapping.items()):
                        self.args.append(val)
                        self.args.append(Expr(amt.OrInstruction, *labelset))
                    return




                case amt.AddInstruction:
                    self._assoc()
                    # now, group like terms, where terms are summands
                    # except a constant multiplication coefficient
                    #TODO: this uses hashing
                    terms = {}
                    for arg in self.args:
                        if arg.op == 0:
                            continue
                        if isinstance(arg.op, int):
                            terms[Expr(1)] = terms.get(Expr(1), 0) + arg.op
                        elif (arg.op == amt.MulInstruction
                                and isinstance(arg.left.op, int)):
                            if len(arg.args) > 2:
                                e = Expr(amt.MulInstruction, *arg.args[1:], reduce=False)
                            else:
                                e = arg.right
                            terms[e] = terms.get(e, 0) + arg.left.op
                        else:
                            terms[arg] = terms.get(arg, 0) + 1

                    self.args = sorted(Expr(amt.MulInstruction, Expr(coef), term)
                            for term, coef in terms.items() if coef != 0)
                    
                    if len(self.args) == 0:
                        self.op = 0
                        break
                    if len(self.args) == 1:
                        self.op = self.left.op
                        self.args = self.left.args
                        break

                case amt.SubInstruction:
                    # a - b = a + (-1)*b
                    self.op = amt.AddInstruction
                    self.right = Expr(amt.MulInstruction, Expr(-1), self.right)
                    continue

                case amt.MulInstruction:
                    self._assoc()
                    if self._distribute(amt.AddInstruction):
                        continue
                    # use commutativity to reorganise factors and group consts
                    const = 1
                    kept = []
                    for arg in self.args:
                        if isinstance(arg.op, int):
                            const *= arg.op
                            if const == 0:
                                break
                        else:
                            kept.append(arg)
                    if const == 0 or len(kept) == 0:
                        self.op = const
                        self.args = []
                        break
                    if const != 1:
                        kept.append(Expr(const))
                    self.args = sorted(kept)

                    if len(self.args) == 1:
                        self.op = self.left.op
                        self.args = self.left.args

                case amt.DivInstruction:
                    if self.right.op == 0:
                        raise OptError("Division by zero discovered.")
                    if self.right.op == 1:
                        # a / 1 = a
                        self.op = self.left.op
                        self.args = self.left.args
                        break
                    if self.left.op == 0:
                        # 0 / a = 0
                        self.op = 0
                        self.args = []
                        break
                    if self.right.op == -1:
                        # a / (-1) = (-1) * a
                        self.op = amt.MulInstruction
                        self.right = self.left
                        self.left = Expr(-1)
                        continue
                    if self.left == self.right:
                        # a / a = 1
                        self.op = 1
                        self.args = []
                        break
                    if isinstance(self.left.op, int) and isinstance(self.right.op, int):
                        self.op = self.left.op // self.right.op
                        self.args = []
                        break

                case amt.ModInstruction:
                    if self.right.op == 0:
                        raise OptError("Modulo zero discovered.")
                    if (self.left.op == 0
                            or (isinstance(self.right.op, int)
                                and abs(self.right.op) == 1)
                            or self.left == self.right):
                        # 0 % b = 0
                        # a % 1 = a % (-1) = 0
                        # a % a = 0
                        self.op = 0
                        self.args = []
                        break
                    if isinstance(self.left.op, int) and isinstance(self.right.op, int):
                        self.op = self.left.op % self.right.op
                        self.args = []
                        break

                case amt.AndInstruction:
                    self._assoc()
                    if self._distribute(amt.OrInstruction, amt.XOrInstruction):
                        continue

                    # use commutativity to collapse dupes and reduce consts
                    #TODO: uses hashing
                    const = -1
                    argset = set()
                    for arg in self.args:
                        if isinstance(arg.op, int):
                            const &= arg.op
                            if const == 0:
                                break
                        else:
                            argset.add(arg)
                    if const == 0 or len(argset) == 0:
                        # and with zero is zero
                        self.op = const
                        self.args = []
                        break
                    if const != -1:
                        argset.add(Expr(const))
                    self.args = sorted(argset)

                    if len(self.args) == 1:
                        self.op = self.left.op
                        self.args = self.left.args
                        break

                case amt.OrInstruction:
                    self._assoc()

                    # use commutativity to collapse dupes and reduce consts
                    const = 0
                    argset = set()
                    for arg in self.args:
                        if isinstance(arg.op, int):
                            const |= arg.op
                            if const == -1:
                                break
                        else:
                            argset.add(arg)
                    if const == -1 or len(argset) == 0:
                        # or with -1 is -1
                        self.op = const
                        self.args = []
                        break
                    if const != 0:
                        argset.add(Expr(const))
                    self.args = sorted(argset)

                    #TODO: absorption? a | (a & b) = a

                    if len(self.args) == 1:
                        self.op = self.left.op
                        self.args = self.left.args

                case amt.XOrInstruction:
                    self._assoc()

                    # use commutativity to cancel dupes and reduce consts
                    const = 0
                    argset = set()
                    for arg in self.args:
                        if isinstance(arg.op, int):
                            const ^= arg.op
                        else:
                            try:
                                argset.remove(arg)
                            except KeyError:
                                argset.add(arg)
                    if len(argset) == 0:
                        self.op = const
                        self.args = []
                        break
                    if const != 0:
                        argset.add(Expr(const))

                    self.args = sorted(argset)

                    if len(self.args) == 1:
                        self.op = self.left.op
                        self.args = self.left.args

                case amt.LShiftInstruction:
                    if self._distribute_left(
                            amt.AddInstruction,
                            amt.AndInstruction,
                            amt.OrInstruction,
                            amt.XOrInstruction):
                        continue
                    
                    # exponent rules
                    if self.left.op == amt.LShiftInstruction:
                        # (a << b) << c = a << (b + c)
                        self.right = Expr(
                                amt.AddInstruction,
                                self.left.right,
                                self.right)
                        self.left = self.left.left
                        continue
                    if self.left.op == amt.RShiftInstruction:
                        # (a >> b) << b = a
                        if self.left.right == self.right:
                            self.op = self.left.left.op
                            self.args = self.left.left.args
                            break

                    if self.left.op == 0:
                        # 0 << a = 0
                        self.op = 0
                        self.args = []
                        break

                    if isinstance(self.right.op, int):
                        if isinstance(self.left.op, int):
                            self.op = self.left.op << self.right.op
                            self.args = []
                            break
                        if (n := self.right.op) >= 0:
                            # a << n = (2**n) * a
                            self.op = amt.MulInstruction
                            self.right = self.left
                            self.left = Expr(2**n)
                            continue
                        # a << (-n) = a >> n
                        self.right.op *= -1
                        self.op = amt.RShiftInstruction

                case amt.RShiftInstruction:
                    if self._distribute_left(
                            amt.AndInstruction,
                            amt.OrInstruction,
                            amt.XOrInstruction):
                        continue

                    # exponent rules
                    if self.left.op == amt.LShiftInstruction:
                        # (a << b) >> c = a << (b - c)
                        self.right = Expr(
                                amt.SubInstruction,
                                self.left.right,
                                self.right)
                        self.left = self.left.left
                        self.op = amt.LShiftInstruction
                        continue
                    if self.left.op == amt.RShiftInstruction:
                        # (a >> b) >> c = a >> (b + c)
                        self.right = Expr(
                                amt.AddInstruction,
                                self.left.right,
                                self.right)
                        self.left = self.left.left
                        continue

                    if self.left.op == 0:
                        # 0 >> n = 0
                        self.op = 0
                        self.args = []
                        break

                    if isinstance(self.right.op, int):
                        if isinstance(self.left.op, int):
                            self.op = self.left.op >> self.right.op
                            self.args = []
                            break
                        if self.right.op <= 0:
                            # a >> (-n) = a << n
                            self.op = amt.LShiftInstruction
                            self.right.op *= -1
                            continue

                case amt.EqInstruction:
                    if self.left == self.right:
                        self.op = 1
                        self.args = []
                        break
                    if isinstance(self.left.op, int) and isinstance(self.right.op, int):
                        self.op = 0
                        self.args = []
                        break
                    if self.left.op != 0:
                        self.right = Expr(amt.SubInstruction, self.right, self.left)
                        self.left = Expr(0)
                        continue

                case amt.NeqInstruction:
                    if self.left == self.right:
                        self.op = 0
                        self.args = []
                        break
                    if isinstance(self.left.op, int) and isinstance(self.right.op, int):
                        self.op = 1
                        self.args = []
                        break
                    if self.left.op != 0:
                        self.right = Expr(amt.SubInstruction, self.right, self.left)
                        self.left = Expr(0)
                        continue

                case amt.LtInstruction:
                    if self.left == self.right:
                        self.op = 0
                        self.args = []
                        break
                    if isinstance(self.left.op, int) and isinstance(self.right.op, int):
                        self.op = self.left.op < self.right.op
                        self.args = []
                        break
                    if self.left.op != 0:
                        self.right = Expr(amt.SubInstruction, self.right, self.left)
                        self.left = Expr(0)
                        continue

                case amt.LeqInstruction:
                    if self.left == self.right:
                        self.op = 1
                        self.args = []
                        break
                    if isinstance(self.left.op, int) and isinstance(self.right.op, int):
                        self.op = self.left.op <= self.right.op
                        self.args = []
                        break
                    if self.left.op != 0:
                        self.right = Expr(amt.SubInstruction, self.right, self.left)
                        self.left = Expr(0)
                        continue

                case _:
                    # shouldn't happen
                    pass

            # after all the reductions happen, exit the loop
            break
    

    ## associativity ##
    @(Syntax(object) >> None)
    def _assoc(self):
        """
        Assuming expression is associative, regroups expression as
        a . (b . c) = a . b . c
        (a . b) . c = a . b . c
        """
        newargs = []
        for arg in self.args:
            if arg.op == self.op:
                newargs.extend(arg.args)
            else:
                newargs.append(arg)
        self.args = newargs
    
    ## distributivity ##
    @(Syntax(object, type, ...) >> bool)
    def _distribute(self, *ops):
        """
        Distributes self.op over the ops specified, and return True
        if distribution occurs
        """
        for i, arg in enumerate(self.args):
            op = self.op
            if arg.op in ops:
                # a . (b : c) . d = (a . b . d) : (a . c . d)
                self.op = arg.op
                self.args = [Expr(op, *self.args[:i], aa, *self.args[i+1:])
                        for aa in arg.args]
                return True
        return False

    @(Syntax(object, type, ...) >> bool)
    def _distribute_left(self, *ops):
        """
        Distributes (a : b) . c = (a . c) : (b . c)
        """
        if self.left.op in ops:
            op = self.op
            self.op = self.left.op
            self.args = [Expr(op, arg, self.right) for arg in self.left.args]
            return True
        return False

class ExprUI:
    """
    Wrapper for Expr for easy user testing
    """
    def __init__(self, expr):
        if isinstance(expr, Expr):
            self.expr = expr
        else:
            self.expr = Expr(expr)

    def __repr__(self):
        return repr(self.expr) + '~'

    def _op(self, op, other):
        return ExprUI(Expr(op, self.expr, other.expr))

    def __add__(self, other):
        return self._op(amt.AddInstruction, other)
    def __sub__(self, other):
        return self._op(amt.SubInstruction, other)
    def __mul__(self, other):
        return self._op(amt.MulInstruction, other)
    def __truediv__(self, other):
        return self._op(amt.DivInstruction, other)
    def __mod__(self, other):
        return self._op(amt.ModInstruction, other)
    
    def __and__(self, other):
        return self._op(amt.AndInstruction, other)
    def __or__(self, other):
        return self._op(amt.OrInstruction, other)
    def __xor__(self, other):
        return self._op(amt.XOrInstruction, other)
    def __lshift__(self, other):
        return self._op(amt.LShiftInstruction, other)
    def __rshift__(self, other):
        return self._op(amt.RShiftInstruction, other)

    def __eq__(self, other):
        return self._op(amt.EqInstruction, other)
    def __ne__(self, other):
        return self._op(amt.NeqInstruction, other)
    def __lt__(self, other):
        return self._op(amt.LtInstruction, other)
    def __le__(self, other):
        return self._op(amt.LeqInstruction, other)

class Comparisons:
    """
    Data structure for a conjunction of several equalities and inequalities.
    Values are stored in a DAG, where nodes represent equality classes of these
    values, and there is an edge from a to b iff a <= b.

    It's not very efficient (consecutive assertions %n <= %(n+1) for n=1...N
    runs in O(N^2)), but the expectation is that these will be fairly small in general.
    """
    #TODO: to avoid computing the transitive closure of any inequality assertion
    # we can instead only do these when 1. a new equality class is discovered, or
    # 2. when a comparison is with an integer. Otherwise, use a DFS and build
    # shortcuts only on "leq" queries

    def __init__(self):
        self._eq = {} # union-find dict for equality classes
        self._leq = {} # leq[a] consists of all things less than a
        self._geq = {} # geq[a] consists of all things greater than a
        self._neq = {}
        self._consistent = True
        self._int_range = {} # int_range[a] = [lo, hi] interval

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
        if node not in self:
            self._eq[node] = node
            self._leq[node] = {node}
            self._geq[node] = {node}
            self._neq[node] = set()
            if isinstance(node.op, int):
                self._int_range[node] = (node.op, node.op)
            else:
                self._int_range[node] = (None, None)

    @(Syntax(object, Expr, (int, None), (int, None)) >> None)
    def _update_int_range(self, node, newlo, newhi):
        node = self.eqclass(node)
        lo, hi = self._int_range[node]
        old = (lo, hi)
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
            if lo == hi:
                self._eq[node] = self.eqclass(Expr(lo))
            if lo > hi:
                self._consistent = False

        self._int_range[node] = (lo, hi)

        if lo != old[0]:
            for gt in self._geq[node]:
                self._update_int_range(gt, lo, None)
        if hi != old[1]:
            for lt in self._leq[node]:
                self._update_int_range(lt, None, hi)

    @(Syntax(object, Expr) >> Expr)
    def eqclass(self, node):
        if node not in self:
            self.add(node)
        if isinstance(node.op, int):
            return node

        # union-find
        head = self._eq[node]
        if (top := self._eq[head]) != head:
            top = self.eqclass(head)
            self._eq[head] = top
            self._eq[node] = top
            head = top

        if head != node and node in self._leq:
            # node used to be the head
            # so now we need to push the data up
            for lt in self._leq.pop(node):
                lt = self.eqclass(lt)
                if lt not in self._leq[head]:
                    self.assert_leq(lt, head)
            for gt in self._geq.pop(node):
                gt = self.eqclass(gt)
                if gt not in self._geq[head]:
                    self.assert_leq(head, gt)
            for neq in self._neq.pop(node):
                self.assert_neq(head, neq)
            lo, hi = self._int_range.pop(node)
            self._update_int_range(head, lo, hi)

        return head

    @(Syntax(object, Expr, Expr) >> None)
    def assert_leq(self, a, b):
        a = self.eqclass(a)
        b = self.eqclass(b)

        self._geq[a].add(b)
        self._leq[b].add(a)

        for lt in self._leq[a]:
            lt = self.eqclass(lt)
            self._leq[b].add(lt)
            self._geq[lt].add(b)

        for gt in self._geq[b]:
            gt = self.eqclass(gt)
            self._leq[gt].add(a)
            self._geq[a].add(gt)

        lo, _ = self._int_range[a]
        _, hi = self._int_range[b]
        self._update_int_range(a, None, hi)
        self._update_int_range(b, lo, None)

        if self.leq(b, a):
            # they now form an equivalence class
            rep = a if isinstance(a.op, int) else b
            self._eq[a] = rep
            self._eq[b] = rep
            for gt in self._geq[rep]:
                if self.leq(gt, b):
                    self._eq[gt] = rep
            for lt in self._leq[rep]:
                if self.leq(a, lt):
                    self._eq[lt] = rep

    @(Syntax(object, Expr, Expr) >> None)
    def assert_eq(self, a, b):
        self.assert_leq(a, b)
        self.assert_leq(b, a)

    @(Syntax(object, Expr, Expr) >> None)
    def assert_neq(self, a, b):
        a = self.eqclass(a)
        b = self.eqclass(b)
        if a == b:
            self._consistent = False
            return
        self._neq[a].add(b)
        self._neq[b].add(a)
        self._update_int_range(a, None, None)
        self._update_int_range(b, None, None)
    
    @(Syntax(object, Expr, Expr) >> bool)
    def leq(self, a, b):
        """
        Return True if a is provably leq b
        """
        a = self.eqclass(a)
        b = self.eqclass(b)
        if a in self._leq[b]:
            return True
        if self._int_range[a][1] is None or self._int_range[b][0] is None:
            return False
        if self._int_range[a][1] <= self._int_range[b][0]:
            self._leq[b].add(a)
            self._geq[a].add(b)
            return True
        return False
    
    @(Syntax(object, Expr, Expr) >> bool)
    def eq(self, a, b):
        """
        Return True if a is provably equal to b
        """
        return self.leq(a, b) and self.leq(b, a)

    @(Syntax(object, Expr, Expr) >> bool)
    def neq(self, a, b):
        """
        Return True if a is provably not equal to b
        """
        a = self.eqclass(a)
        b = self.eqclass(b)
        return a in self._neq[b]
