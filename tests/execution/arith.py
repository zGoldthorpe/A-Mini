import sys

from tests.execution.env import ExecutionTestSuite

ts = ExecutionTestSuite("execution/arith")

ts.simulate("%a = 2",
            "%b = 5",
            "%c = -3",
            "%sum = %a + %b",
            "%diff = %a - %c",
            "%prod = %b * %c",
            expected={
                "%a" : 2,
                "%b" : 5,
                "%c" : -3,
                "%sum" : 7,
                "%diff" : 5,
                "%prod" : -15,
                })

ts.simulate("%0 = -5",
            "%1 = 3",
            "%sum = %0 + 5",
            "%sum.1 = 4 + %1",
            "%diff = 3 - 10",
            "%diff.1 = -1--1",
            "%diff.2 = -1-1",
            "%prod = 0*0",
            "%prod.1 = %0*%1",
            expected={
                "%0" : -5,
                "%1" : 3,
                "%sum" : 0,
                "%sum.1" : 7,
                "%diff" : -7,
                "%diff.1" : 0,
                "%diff.2" : -2,
                "%prod" : 0,
                "%prod.1" : -15,
                })

if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
