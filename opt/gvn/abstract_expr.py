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
    @(Syntax(object) >> (int,str))
    def value(self):
        return self.op

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
            rep = str(self.value)
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
