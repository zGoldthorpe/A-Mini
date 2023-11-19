"""
Abstract expressions
======================
Goldthorpe

This module provides a datatype for managing abstract computation expressions,
primarily for value numbering.
"""

import builtins

from utils.syntax import Syntax
from opt.tools import OptError

import ampy.types as amt

class Expr:
    # forward declaration
    pass

class Expr(Expr):
    """
    Formal computational expression, with rewriting rules
    """
    @(Syntax(object, str, ...) >> None)
    def __init__(self, primitive='0', /):
        # an expression is an AST, whose leaf nodes are constants
        # or virtual registers
        #
        # op: type of operation
        #   - int: integer
        #   - str: register
        #   - instruction class: corresponding operation
        # left: first operand
        # right: second operand
        if primitive.startswith('%'):
            self.op = str
            self.left = primitive
        else:
            self.op = int
            self.left = int(primitive)
        self.right = None

    @classmethod
    @(Syntax(object, type, Expr, Expr) >> Expr)
    def genexpr(cls, opclass, left, right):
        """
        Build an expression from a binary operation (specified by
        its instruction class) and expression operands
        """
        expr = Expr.__new__(Expr)
        expr.op = opclass
        expr.left = left
        expr.right = right
        expr.rewrite()
        return expr

    def __str__(self):

        match self.op:
            
            case builtins.int:
                # integer
                return str(self.left)

            case builtins.str:
                # register
                return self.left

            case T if issubclass(T, amt.BinaryInstructionClass):
                return f"({self.left} {T.op} {self.right})"
            
            case T:
                # shouldn't happen
                return f"({self.left} {T} {self.right})"

    def __repr__(self):
        return f"Expr<{self}>"

    @(Syntax(object, Expr) >> int)
    def compare(self, other):
        """
        Returns -1, 0, 1 if self is lt, eq, or gt other, resp.
        Total ordering is fairly arbitrary
        """
        def cmp(a, b):
            return (a > b) - (a < b)

        if self.op == other.op:
            if self.op in (int, str):
                return cmp(self.left, other.left)
            if (res := self.left.compare(other.left)) != 0:
                return res
            return self.right.compare(other.right)

        order = (
                builtins.int,
                builtins.str,
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
                )

        for op in order:
            if self.op == op:
                return -1
            if other.op == op:
                return +1

        # they were both of an unrecognised type at this point
        raise NotImplementedError





    @(Syntax(object) >> None)
    def rewrite(self):
        """
        Apply rewriting rules to simplify expression.
        The assumption/invariant is that the operands are already
        fully simplified.
        """
        # rewriting rules implemented:
        # redundancy: a - b = a + (-1)*b
        # commutativity: +, *, &, |, ^, ==, !=
        # associativity: +, *, &, |, ^
        # 2-sided distributivity: (*,+), (&,|^)
        #              (we do not distribute (|,&) as this
        #               would result in infinite expansion)
        # left distributivity: (<<,+&|^), (>>,&|^)
        
        if self.op in (int, str):
            return

        cmp = self.left.compare(self.right)
        if cmp == 0:
            self._simplify_eq()
            return # the subexprs are fully simplified already
        if cmp == 1:
            if self.op in (
                    amt.AddInstruction,
                    amt.MulInstruction,
                    amt.AndInstruction,
                    amt.OrInstruction,
                    amt.XOrInstruction,
                    amt.EqInstruction,
                    amt.NeqInstruction):
                self.left, self.right = self.right, self.left

        while True:

            match self.op:
                case amt.AddInstruction:
                    if self._reassociate():
                        continue
                    
                    # group like terms, but only if
                    # the coefficient is constant
                    if (self.left.op == amt.MulInstruction
                            and self.left.left.op == int):
                        cmp = self.right.compare(self.left.right)
                        if cmp == 0:
                            # (n * a) + a = (n+1) * a
                            self.op = amt.MulInstruction
                            self.left = Expr(str(self.left.left.left + 1))
                            continue
                    elif (self.right.op == amt.MulInstruction
                            and self.right.left.op == int):
                        cmp = self.left.compare(self.right.right)
                        if cmp == 0:
                            # a + (n * a) = (n+1) * a
                            self.op = amt.MulInstruction
                            self.right = Expr(str(self.right.left.left + 1))
                            self.left, self.right = self.right, self.left
                            # swap is necessary

                case amt.SubInstruction:
                    # a - b = a + (-1)*b
                    self.op = amt.AddInstruction
                    self.right = Expr.genexpr(
                            amt.MulInstruction,
                            Expr("-1"),
                            self.right)
                    continue

                case amt.MulInstruction:
                    if self._reassociate():
                        continue
                    if self._distribute(
                            amt.AddInstruction):
                        continue

                case amt.DivInstruction:
                    pass

                case amt.ModInstruction:
                    pass

                case amt.AndInstruction:
                    if self._reassociate():
                        continue
                    if self._distribute(
                            amt.OrInstruction,
                            amt.XOrInstruction):
                        continue

                case amt.OrInstruction:
                    if self._reassociate():
                        continue
                    #TODO absorption: a | (a & b) = a

                case amt.XOrInstruction:
                    if self._reassociate():
                        continue

                case amt.LShiftInstruction:
                    if self._distribute_left(
                            amt.AddInstruction,
                            amt.AndInstruction,
                            amt.OrInstruction,
                            amt.XOrInstruction):
                        continue
                    #TODO:
                    # (a << b) << c = a << (b + c)
                    # (a << b) >> c = a << (b - c)

                case amt.RShiftInstruction:
                    if self._distribute_left(
                            amt.AndInstruction,
                            amt.OrInstruction,
                            amt.XOrInstruction):
                        continue
                    #TODO:
                    # (a >> b) >> c = a >> (b + c)
                    # (a >> b) << b = a

                #TODO: for comparisons, move everything
                # to the RIGHT (since 0 is a const, it should
                # be on the left)

                case _:
                    pass

            self._eval() # now evaluate constant expressions

            if self.op != int:
                if self.left.op == int:
                    self._simplify_left()
                if self.right.op == int:
                    self._simplify_right()
            return

    @(Syntax(object) >> None)
    def _eval(self):
        """
        If both operands are integers, then just evaluate
        """
        if self.left.op != int or self.right.op != int:
            return

        lhs = self.left.left
        rhs = self.right.left

        match self.op:
            case amt.AddInstruction:
                self.left = lhs + rhs
            case amt.MulInstruction:
                self.left = lhs * rhs
            case amt.DivInstruction:
                if rhs == 0:
                    raise OptError("Program leads to a division by zero!")
                self.left = lhs // rhs
            case amt.ModInstruction:
                if rhs == 0:
                    raise OptError("Program leads to a modulo by zero!")
                self.left = lhs % rhs
            case amt.AndInstruction:
                self.left = lhs & rhs
            case amt.OrInstruction:
                self.left = lhs | rhs
            case amt.XOrInstruction:
                self.left = lhs ^ rhs
            case amt.LShiftInstruction:
                self.left = lhs << rhs
            case amt.RShiftInstruction:
                self.left = lhs >> rhs
            case amt.EqInstruction:
                self.left = int(lhs == rhs)
            case amt.NeqInstruction:
                self.left = int(lhs != rhs)
            case amt.LtInstruction:
                self.left = int(lhs < rhs)
            case amt.LeqInstruction:
                self.left = int(lhs <= rhs)
            case _:
                return

        # at this point, match successfully evaluated expression
        self.op = int
        self.right = None

    @(Syntax(object) >> None)
    def _simplify_left(self):
        """
        Assumes left operand is an integer, but right operand is not
        """
        match self.left.left:
            case 0:
                match self.op:
                    case (amt.AddInstruction
                            | amt.OrInstruction
                            | amt.XOrInstruction):
                        # 0 + a = a
                        # 0 | a = a
                        # 0 ^ a = a
                        self.op = self.right.op
                        self.left = self.right.left
                        self.right = self.right.right
                    case (amt.MulInstruction
                            | amt.DivInstruction
                            | amt.ModInstruction
                            | amt.AndInstruction
                            | amt.LShiftInstruction
                            | amt.RShiftInstruction):
                        # 0 * a = 0
                        # 0 / a = 0
                        # 0 % a = 0
                        # 0 & a = 0
                        # 0 << a = 0
                        # 0 >> a = 0
                        self.op = int
                        self.left = 0
                        self.right = None
                    case _:
                        # other cases have no reductions
                        pass
            case 1:
                if self.op == amt.MulInstruction:
                    # 1 * a = a
                    self.op = self.right.op
                    self.left = self.right.left
                    self.right = self.right.right
            case -1:
                match self.op:
                    case amt.AndInstruction:
                        # (-1) & a = a
                        self.op = self.right.op
                        self.left = self.right.left
                        self.right = self.right.right
                    case (amt.OrInstruction
                            | amt.RShiftInstruction):
                        # (-1) | a = (-1)
                        # (-1) >> a = (-1)
                        self.op = int
                        self.left = -1
                        self.right = None
                    case _:
                        pass
            case _:
                pass

    @(Syntax(object) >> None)
    def _simplify_right(self):
        """
        Assumes right operand is an integer, but left operand
        is not, which restricts our attention to noncommutative
        operations, as the commutative operands are sorted so that
        constants are on the left.
        """
        rarg = self.right.left
        match self.op:
            case amt.DivInstruction:
                if rarg == 0:
                    raise OptError("Program leads to a division by zero!")
                elif rarg == 1:
                    # a / 1 = a
                    self.op = self.left.op
                    self.right = self.left.right
                    self.left = self.left.left
                elif rarg == -1:
                    # a / (-1) = (-1) * a
                    self.op = amt.MulInstruction
                    self.right = self.left
                    self.left = Expr("-1")
                    # this may lead to some further simplification
                    self.rewrite()
            case amt.ModInstruction:
                if rarg == 0:
                    raise OptError("Program leads to modulo by zero!")
                elif abs(rarg) == 1:
                    # a % 1 = a % (-1) = 0
                    self.op = int
                    self.left = 0
                    self.right = None
            case amt.LShiftInstruction:
                if rarg == 0:
                    # a << 0 = a
                    self.op = self.left.op
                    self.right = self.left.right
                    self.left = self.left.left
                elif rarg > 0:
                    # a << n = (2**n)*a
                    self.op = amt.MulInstruction
                    self.right = self.left
                    self.left = Expr(str(2**rarg))
                    self.rewrite()
                else:
                    # a << (-n) = a >> n
                    self.op = amt.RShiftInstruction
                    self.right.left *= -1
                    self.rewrite()
            case amt.RShiftInstruction:
                if rarg == 0:
                    # a >> 0 = a
                    self.op = self.left.op
                    self.right = self.left.right
                    self.left = self.left.left
                elif rarg < 0:
                    # a >> (-n) = (2**n)*a
                    self.op = amt.MulInstruction
                    self.right = self.left
                    self.left = Expr(str(2**(-rarg)))
                    self.rewrite()

    @(Syntax(object) >> None)
    def _simplify_eq(self):
        """
        On the assumption that the two operands are equal, simplifies the computation.
        Recursively rewrites if necessary
        """
        match self.op:
            case (amt.SubInstruction
                    | amt.ModInstruction
                    | amt.XOrInstruction
                    | amt.NeqInstruction
                    | amt.LtInstruction):
                # a - a = 0
                # a % a = 0
                # a ^ a = 0
                # (a != a) = 0
                # (a < a) = 0
                self.op = int
                self.left = 0
                self.right = None
            case (amt.DivInstruction
                    | amt.EqInstruction
                    | amt.LeqInstruction):
                # assuming division is well-defined
                # a / a = 1
                # (a == a) = 1
                # (a <= a) = 1
                self.op = int
                self.left = 1
                self.right = None
            case (amt.AndInstruction
                    | amt.OrInstruction):
                # a & a = a; 
                # a | a = a;
                self.op = self.left.op
                self.right = self.left.right
                self.left = self.left.left
            case amt.AddInstruction:
                # a + a = 2 * a
                self.op = amt.MulInstruction
                self.left = Expr("2")
                self.rewrite()
            case _:
                # other cases have no simplification
                pass

    @(Syntax(object) >> bool)
    def _reassociate(self):
        """
        Assumes expr op is associative and tries to rewrite
        a . (b . c) => (a . b) . c
        Return whether or not the transformation happened
        """
        if self.right.op != self.op:
            return False
        self.left = Expr.genexpr(
                self.op,
                self.left,
                self.right.left)
        self.right = self.right.right
        return True

    @(Syntax(object, type, ...) >> bool)
    def _distribute_left(self, *opclasses):
        """
        Checks if expr is of the form (a : b) . c where (:) is
        in the list of permissible opclasses.
        Then rewrites the expression as
        (a . c) : (b . c)
        """
        if (op := self.left.op) not in opclasses:
            return False
        rhs = self.right
        self.right = Expr.genexpr(
                self.op,
                self.left.right,
                rhs)
        self.left = Expr.genexpr(
                self.op,
                self.left.left,
                rhs)
        self.op = op
        return True

    @(Syntax(object, type, ...) >> bool)
    def _distribute_right(self, *opclasses):
        """
        Checks if expr is of the form a . (b : c) where (:) is
        in the list of permissible opclasses.
        Then rewrites the expression as
        (a . b) : (a . c)
        """
        if (op := self.right.op) not in opclasses:
            return False
        lhs = self.left
        self.left = Expr.genexpr(
                self.op,
                lhs,
                self.right.left)
        self.right = Expr.genexpr(
                self.op,
                lhs,
                self.right.right)
        self.op = op
        return True

    @(Syntax(object, type, ...) >> bool)
    def _distribute(self, *opclasses):
        """
        Combination of dist left and dist right
        """
        return self._distribute_left(*opclasses) or self._distribute_right(*opclasses)


