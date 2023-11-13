import sys

from tests.execution.env import ExecutionTestSuite

ts = ExecutionTestSuite("execution/branch")

ts.simulate("@0: goto @label",
            "@label: exit")

ts.simulate("@0: %cond = 1",
            "branch %cond ? @lbl1 : @lbl2",
            "@lbl1: %a = 5",
            "exit",
            "@lbl2: %a = 10",
            expected={"%a" : 5})

ts.simulate("@0: %cond=0",
            "branch%cond?@lbl1:@lbl2",
            "@lbl1:%a=5",
            "exit",
            "@lbl2:%a=10",
            expected={"%a" : 10})

ts.simulate("@0: %cond=-1",
            "branch%cond?@lbl1:@lbl2",
            "@lbl1:%a=5",
            "exit",
            "@lbl2:%a=10",
            expected={"%a" : 5})

ts.simulate("@0:",
            "branch 1 ? @A : @B",
            "@A: %a = 5",
            "branch 0 ? @C : @D",
            "@B: %a = 10",
            "goto @C",
            "@C: %b = 5",
            "exit",
            "@D: %b = 10",
            expected={"%a" : 5, "%b" : 10})

if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
