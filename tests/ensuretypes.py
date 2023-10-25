import sys

from ampy.ensuretypes import Syntax
from tests.tools import PythonExecutionTestSuite

ts = PythonExecutionTestSuite("ensure-types")

ts.exec("@Syntax(int)\ndef foo(x): return x",
        "foo(0)",
        "try:\n\tfoo('a')\nexcept TypeError:\n\tsafe=True",
        "assert safe == True",
        state=dict(Syntax=Syntax))

#TODO more tests

if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
