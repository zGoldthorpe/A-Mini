import sys

from tests.execution.env import ExecutionTestSuite

ts = ExecutionTestSuite("execution/phi")

ts.simulate("@0: goto @A",
            "@A: goto @B",
            "@B: %p = phi [3, @A]",
            expected = {"%p" : 3})

ts.simulate("@0: goto @A",
            "@A: goto @B",
            "@B: goto @C",
            "@C: %p = phi [3, @A], [-1, @B]",
            expected = {"%p" : -1})

ts.simulate("@0: goto @jmp",
            "@jmp: goto @jmp.2",
            "@jmp.2: goto @jmp.3",
            "@jmp.3: %p = phi [-6, @jmp], [3,@jmp.3], [ 0, @jmp.2 ]",
            expected = {"%p" : 0})

ts.simulate("@0:",
            "%0 = 6",
            "%1 = 8",
            "goto @jmp",
            "@jmp: goto @jmp.2",
            "@jmp.2: %p = phi [ %0, @jmp], [ %1, @jmp.2 ]",
            expected = {"%p" : 6})

if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
