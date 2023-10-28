import sys

from tests.execution.env import ExecutionTestSuite, InputSimulator, OutputTester

stdin = InputSimulator()
stdout = OutputTester()
brkpt = BreakpointTester()
ts = ExecutionTestSuite("execution/debug",
        read_handler=stdin,
        write_handler=stdout,
        brk_handler=brkpt)

brkpt.push_brk("breakpoint", dict())
ts.simulate("brkpt !breakpoint",
            onexit="assert len(brkpt) == 0",
            onexitlocals=dict(brkpt=brkpt))
brkpt.clear() # just in case

brkpt.push_brk("0", {'%a' : 1})
brkpt.push_brk("1", {'%a' : 1, '%b' : 5})
ts.simulate("%a = 1",
            "brkpt !0",
            "%b = 5",
            "brkpt !1",
            expected={"%a" : 1, "%b" : 5},
            onexit="assert len(brkpt) == 0",
            onexitlocals=dict(brkpt=brkpt))
brkpt.clear()

stdin.push_input(5,4)
brkpt.push_brk("after.read", {'%a' : 5})
brkpt.push_brk("before.write", {'%a' : 5, '%b' : 4, '%c' : 9})
brkpt.push_brk("at.end", {'%a' : 5, '%b' : 4, '%c' : 9})
ts.simulate("read %a",
            "brkpt !after.read",
            "read %b",
            "%c = %a + %b",
            "brkpt !before.write",
            "write %c",
            "brkpt !at.end",
            expected = {'%a' : 5, '%b' : 4, '%c' : 9},
            onexit="assert len(brkpt) == len(stdin) == len(stdout) == 0",
            onexitlocals=dict(brkpt=brkpt, stdin=stdin, stdout=stdout))
brkpt.clear()
stdin.clear()
stdout.clear()


if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
