import sys
import traceback

from opt.gvn.abstract_expr import (
        Expr as E,
        Comparisons as C,
        )

from tests.tools import TestSuite

class CompAssessmentTestSuite(TestSuite):

    def __repr__(self):
        return f"CompAssessmentTestSuite({self.name})"

    @TestSuite.test
    def build_and_test(self, build, tests):
        """
        `build` is a list of (func, args) pairs.
        `tests` is a list of (func, args, expected) pairs.
        The build expressions are done sequentially, and can only fail on
        error.
        The test expressions must yield `expected` to pass
        """
        for i, b in enumerate(build):
            func = b[0]
            args = b[1:]
            try:
                func(*args)
            except Exception as e:
                self._error(f"Calling {func.__name__}{args} on line {i} of building threw an exception {type(e).__name__}")
                return False, dict(
                        type="build-error",
                        exception=Exception(e),
                        func=func,
                        args=args,
                        line=i,
                        traceback=traceback.format_exc())
        for i, t in enumerate(tests):
            func = t[0]
            args = t[1:-1]
            expected = t[-1]
            try:
                res = func(*args)
            except Exception as e:
                self._error(f"Calling {func.__name__}{args} on line {i} of testing threw an exception {e.__name__}")
                return False, dict(
                        type="test-error",
                        exception=Exception(e),
                        func=func,
                        args=args,
                        line=i,
                        traceback=traceback.format_exc())
            if res != expected:
                self._error(f"Test {func.__name__}{args} = {res}, expected {expected}.")
                return False, dict(
                        type="test-wrong-answer",
                        value=res,
                        expected=expected,
                        func=func,
                        args=args,
                        line=i)
        return True, {}

ts = CompAssessmentTestSuite("abstract_comparisons")

w = E('w')
x = E('x')
y = E('y')
z = E('z')

c = C()
ts.build_and_test(
        [
            (c.add, w),
            (c.add, x),
            (c.add, y),
            (c.add, z),
            (c.assert_leq, w, x),
            (c.assert_leq, w, y),
            (c.assert_leq, y, z),
            (c.assert_leq, z, w),
        ],
        [
            (c.leq, w, x, True),
            (c.leq, z, x, True),
            (c.leq, z, y, True),
            (c.eq, z, w, True),
            (c.leq, x, z, False),
            (c.is_consistent, True)
        ])

c = C()
ts.build_and_test(
        [
            (c.add, w),
            (c.add, x),
            (c.add, y),
            (c.add, z),
            (c.assert_leq, w, x),
            (c.assert_leq, w, y),
            (c.assert_leq, y, E(5)),
            (c.assert_leq, E(1), x),
            (c.assert_leq, E(-1), w),
        ],
        [
            (c.leq, E(-1), x, True),
            (c.leq, E(1), w, False),
            (c.leq, w, E(5), True),
            (c.leq, w, E(10), True),
            (c.leq, x, E(10), False),
            (c.is_consistent, True),
        ])

c = C()
ts.build_and_test(
        [
            (c.add, w),
            (c.add, x),
            (c.add, y),
            (c.assert_leq, w, x),
            (c.assert_leq, x, y),
            (c.assert_leq, y, E(-5)),
            (c.assert_leq, E(0), w),
        ],
        [
            (c.is_consistent, False),
        ])

c = C()
ts.build_and_test(
        [
            (c.assert_leq, x, E(1)),
            (c.assert_leq, E(-1), x),
            (c.assert_neq, x, E(-1)),
            (c.assert_neq, x, E(1)),
        ],
        [
            (c.eq, x, E(0), True),
            (c.is_consistent, True),
        ])

c = C()
ts.build_and_test(
        [
            (c.assert_leq, w, x),
            (c.assert_leq, x, E(1)),
            (c.assert_leq, E(0), w),
            (c.assert_neq, w, E(0)),
        ],
        [
            (c.eq, x, E(1), True),
            (c.is_consistent, True),
        ])

if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
