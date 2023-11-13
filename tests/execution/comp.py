import sys

from tests.execution.env import ExecutionTestSuite

ts = ExecutionTestSuite("execution/comp")

ts.simulate("@0:",
            "%a = 1",
            "%b = -3",
            "%c = 6",
            "%eq = %a == %b",
            "%eq.1 = %a == 1",
            "%eq.2 = -3 == %b",
            "%eq.3 = -2==-2",
            "%neq = %b != %b",
            "%lt = %b < 0",
            "%lt.2 = %c < 6",
            "%leq = %c <= 6",
            "%leq.2 = %b <= 0",
            "%leq.3 = 2 <= %a",
            expected={
                "%a" : 1,
                "%b" : -3,
                "%c" : 6,
                "%eq" : 0,
                "%eq.1" : 1,
                "%eq.2" : 1,
                "%eq.3" : 1,
                "%neq" : 0,
                "%lt" : 1,
                "%lt.2" : 0,
                "%leq" : 1,
                "%leq.2" : 1,
                "%leq.3" : 0,
                })

if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
