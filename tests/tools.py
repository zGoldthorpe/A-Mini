"""
General testing functionality, implemented as-needed
"""
import traceback
import sys

def perror(*args, **kwargs):
    print(f"\033[31m", end='', file=sys.stderr)
    print(*args, **kwargs, file=sys.stderr)
    print("\033[m", end='', file=sys.stderr, flush=True)

def psuccess(*args, **kwargs):
    print(f"\033[32m", end='', file=sys.stderr)
    print(*args, **kwargs, file=sys.stderr)
    print("\033[m", end='', file=sys.stderr, flush=True)


class TestSuite:

    def __init__(self, name):
        self._passes = []
        self._data = []
        self._test_counter = -1
        self.name = name

    def _init_test(self):
        self._test_counter += 1
        self._passes.append(False)
        self._data.append({})

    def _record_result(self, result:bool, **state):
        self._passes[self._test_counter] = result
        for kw in state:
            self._data[self._test_counter][kw] = state[kw]

    @property
    def all_tests_passed(self):
        return all(self._passes)
    
    def print_results(self):
        num_passed = len(filter(None, self._passed))
        num_total = len(self._passed)
        if num_passed == num_total:
            psuccess(f"[{self.name}] Passed")
        else:
            perror(f"[{self.name}] {num_passed} / {num_total} ({100*num_passed/num_total:.2f}%) passed")

    def get_state(self, test):
        assert(self._test_counter >= test)
        return self._data[test]

    def _error(self, *args, **kwargs):
        perror(f"[{self.name}] Test #{self._test_counter:02d}:", *args, **kwargs)

    def _success(self, *args, **kwargs):
        psuccess(f"[{self.name}] Test #{self._test_counter:02d}", *args, **kwargs)

class PythonExecutionTestSuite(TestSuite):

    def exec(self, *lines, state=None, expected=None):
        self._init_test()
        state = dict(locals() if state is None else state)
        for (i, line) in enumerate(lines):
            try:
                exec(line, state)
            except Exception as e:
                self._error(f"""{type(e).__name__} occurred while processing line {i+1}:
\t{line}
Exception: {e}""")
                self._record_result(False,
                        type="exec-error",
                        lines=lines,
                        failed_at=i,
                        exception=Exception(e),
                        exec_state=state,
                        traceback=traceback.format_exc())
                return False
        if expected is not None:
            diff = dict(missing=set(), diff={})
            for var in expected:
                if var not in state:
                    self._error(f"Expected variable {var} not in local state after execution.")
                    diff["missing"].add(var)
                elif state[var] != expected[var]:
                    self._error(f"{var} expected {expected[var]}; got {state[var]}")
                    diff["diff"][var] = dict(expected=expected[var], received=state[var])
            if len(diff["missing"]) + len(diff["diff"]) > 0:
                self._record_result(False,
                        type="exec-diff",
                        lines=lines,
                        diff=diff,
                        exec_state=state)
                return False
        self._record_result(True,
                lines=lines,
                exec_state=state)
        return True
    
    def get_exec_state(self, test):
        return self.get_state(test)["exec_state"]
    
    def inherit_exec_state(self, test, extern_state):
        """
        Passes state from execution #test to extern_state
        E.g., pass extern_state=locals() to instantiate all variables in local scope.
        """
        state = self.get_exec_state(test)
        for kw in state:
            extern_state[kw] = state[kw]




