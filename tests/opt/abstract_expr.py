import sys

from opt.gvn.abstract_expr import Expr

import ampy.types as amt

from tests.tools import TestSuite

class E:
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
        return E(Expr(op, self.expr, other.expr))

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

class ExprAssessmentTestSuite(TestSuite):

    def __repr__(self):
        return f"ExprAssessmentTestSuite({self.name})"

    @TestSuite.test
    def check_equality(self, lhs, rhs):
        """
        Takes two E objects and checks if their underlying
        expressions are equal.
        """
        if lhs.expr == rhs.expr:
            return True, dict(e=lhs)
        self._error(f"Expression mismatch: {lhs.expr} and {rhs.expr}")
        return False, dict(lhs=lhs, rhs=rhs)



ts = ExprAssessmentTestSuite("abstract_expr")

a = E('a')
b = E('b')
c = E('c')

# Addition

ts.check_equality(E(1) + E(1), E(2))
ts.check_equality(E(3) + E(-3), E(0))
ts.check_equality(a + b, b + a)
ts.check_equality((a + b) + c, a + (b + c))
ts.check_equality(a + E(0), a)

# Subtraction
ts.check_equality(E(2) - E(1), E(1))
ts.check_equality(E(5) - E(5), E(0))
ts.check_equality(a - E(0), a)
ts.check_equality(a - b, a + E(-1)*b)

# Multiplication
ts.check_equality(E(2) * E(3), E(6))
ts.check_equality(a * b, b * a)
ts.check_equality((a * b) * c, a * (b * c))
ts.check_equality(a * E(0), E(0))
ts.check_equality(a * E(1), a)

# Polynomials
ts.check_equality(a + a, E(2)*a)
ts.check_equality(E(3)*a + E(5)*a, E(8)*a)
ts.check_equality(a * (b + c), a*b + a*c)
ts.check_equality((a + b)*(a + b), a*a + E(2)*a*b + b*b)
ts.check_equality(E(3)*a*b + b*E(-3)*a, E(0))
ts.check_equality(a*a*a - b*b*b, (a - b)*(a*a + a*b + b*b))
ts.check_equality((a+E(3))*(a-E(4)), (a*a - a - E(12)))
ts.check_equality((a+b+c)*(a+b+c), a*a + b*b + c*c + E(2)*(a*b+a*c+b*c))

# Division and modulo
ts.check_equality(E(13) / E(3), E(4))
ts.check_equality(E(0) / a, E(0))
ts.check_equality(a / E(1), a)
ts.check_equality(a / a, E(1))
ts.check_equality(E(13) % E(3), E(1))
ts.check_equality(E(0) % a, E(0))
ts.check_equality(a % E(1), E(0))
ts.check_equality(a % a, E(0))

# And
ts.check_equality(E(6) & E(11), E(2))
ts.check_equality(a & b, b & a)
ts.check_equality((a & b) & c, a & (b & c))
ts.check_equality(a & a, a)
ts.check_equality(a & E(0), E(0))
ts.check_equality(a & E(-1), a)
ts.check_equality(a & (b | c), (a & b) | (a & c))
ts.check_equality(a & (b ^ c), (a & b) ^ (a & c))

# Or
ts.check_equality(E(6) | E(11), E(15))
ts.check_equality(a | b, b | a)
ts.check_equality((a | b) | c, a | (b | c))
ts.check_equality(a | a, a)
ts.check_equality(a | E(0), a)
ts.check_equality(a | E(-1), E(-1))
#ts.check_equality(a | (b & c), (a | b) & (a | c))
# cannot do both &| and |& distribution, as this would never terminate
# this is an example where Expr is not perfect

# XOr
ts.check_equality(E(6) ^ E(11), E(13))
ts.check_equality(a ^ b, b ^ a)
ts.check_equality((a ^ b) ^ c, a ^ (b ^ c))
ts.check_equality(a ^ a, E(0))
ts.check_equality(a ^ E(0), a)
ts.check_equality(a ^ b ^ c ^ a ^ b, c)

# Bitshifting
ts.check_equality(E(3) << E(5), E(96))
ts.check_equality(E(96) >> E(3), E(12))
ts.check_equality(E(96) >> E(96), E(0))
ts.check_equality((a + b) << c, (a << c) + (b << c))
ts.check_equality((a & b) << c, (a << c) & (b << c))
ts.check_equality((a | b) << c, (a << c) | (b << c))
ts.check_equality((a ^ b) << c, (a << c) ^ (b << c))
ts.check_equality((a & b) >> c, (a >> c) & (b >> c))
ts.check_equality((a | b) >> c, (a >> c) | (b >> c))
ts.check_equality((a ^ b) >> c, (a >> c) ^ (b >> c))
ts.check_equality((a << b) << c, a << (b + c))
ts.check_equality((a << b) >> c, a << (b - c))
ts.check_equality((a >> b) >> c, a >> (b + c))
ts.check_equality((a >> b) << b, a)
ts.check_equality(E(0) << a, E(0))
ts.check_equality(E(0) >> a, E(0))
ts.check_equality(a << E(10), a * E(2**10))
ts.check_equality(a << E(-10), a >> E(10))
ts.check_equality(a >> E(-10), a * E(2**10))

# Comparisons
ts.check_equality(E(3) == E(5), E(0))
ts.check_equality(a == a, E(1))
ts.check_equality(E(3) != E(5), E(1))
ts.check_equality(a != a, E(0))
ts.check_equality(E(3) < E(5), E(1))
ts.check_equality(a < a, E(0))
ts.check_equality(E(3) <= E(5), E(1))
ts.check_equality(a <= a, E(1))


if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
