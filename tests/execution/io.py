import sys

from tests.execution.env import ExecutionTestSuite, InputSimulator, OutputTester

stdin = InputSimulator()
stdout = OutputTester()
ts = ExecutionTestSuite("execution/io",
        read_handler=stdin,
        write_handler=stdout)

stdin.push_input(5)
ts.simulate("@0: read %a",
            expected={"%a" : 5},
            onexit="assert len(stdin) == 0",
            onexitlocals=dict(stdin=stdin))
stdin.clear() # just in case

stdout.push_output(5)
ts.simulate("@0: %a = 5",
            "write %a",
            onexit="assert len(stdout) == 0",
            onexitlocals=dict(stdout=stdout))
stdout.clear()

stdout.push_output(5)
ts.simulate("@0: write 5",
            onexit="assert len(stdout) == 0",
            onexitlocals=dict(stdout=stdout))
stdout.clear()

stdin.push_input(-6)
stdout.push_output(-5)
ts.simulate("@0: read %a",
            "%b = %a + 1",
            "write %b",
            expected = {"%a" : -6, "%b" : -5},
            onexit="assert len(stdin) == len(stdout) == 0",
            onexitlocals=dict(stdin=stdin, stdout=stdout))
stdin.clear()
stdout.clear()

if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
