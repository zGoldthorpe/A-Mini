import sys
import traceback

from tests.opt.gvn_expr import E

from opt.gvn.predicates import PredicatedState as PS

from tests.tools import TestSuite

class PredicatedStateTestSuite(TestSuite):

    def __repr__(self):
        return f"PredicatedStateTestSuite({self.name})"

    @TestSuite.test
    def run(self, ps, lines):
        """
        `ps` - the PredicatedState instance
        `lines` - list of tuples (func, expr:E) or (func, expr:E, expected:E)
        """
        for i, t in enumerate(lines):
            if len(t) == 2:
                func, expr = t
                expected = None
            else:
                func, expr, expected = t

            try:
                ret = func(expr.expr)
            except Exception as e:
                self._error(f"Calling {func.__name__}({expr.expr}) on line {i} resulted in an exception {type(e).__name__}.")
                return False, dict(
                        type="exception",
                        ps=ps,
                        exception=Exception(e),
                        func=func,
                        expr=expr.expr,
                        line=i,
                        traceback=traceback.format_exc())

            if expected is not None and ret != expected.expr:
                self._error(f"{func.__name__}({expr.expr}) = {ret}, but expected {expected.expr}.")
                return False, dict(
                        type="mismatch",
                        ps=ps,
                        func=func,
                        expr=expr.expr,
                        expected=expected.expr,
                        line=i)

        return True, dict(ps=ps)

ts = PredicatedStateTestSuite("predicated_state")

s = E('s')
t = E('t')
u = E('u')
v = E('v')
w = E('w')
x = E('x')
y = E('y')
z = E('z')

ps = PS()
ts.run(ps, [
    (ps.assert_nonzero, s == t),
    (ps.assert_nonzero, t == u),
    (ps.assert_nonzero, u == v),
    (ps.simplify, s == v, E(1)),
    (ps.simplify, t != v, E(0)),
    ])

ps = PS()
ts.run(ps, [
    (ps.assert_nonzero, s <= t),
    (ps.assert_nonzero, t <= u),
    (ps.assert_nonzero, u <= v),
    (ps.simplify, s <= v, E(1)),
    ])

#NB: the comparisons data structure does not handle strict inequalities
#    e.g. it cannot infer from a < b and b < c that a < c; just that a <= c


if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
