"""
General testing functionality, implemented as-needed
"""
import functools
import traceback
import sys

from ampy.printing import psuccess, perror

class TestSuite:
    """
    Generic test suite

    Provides functionality to track tests and store their results
    """

    def __init__(self, name):
        """
        Initialise test suite with specified name
        """
        self._data = []
        self._test_counter = -1
        self.name = name

    def __repr__(self):
        return f"TestSuite({self.name})"

    def _init_test(self, test_name):
        self._test_counter += 1
        self._data.append(dict(test_name=test_name, passed=False, state={}))

    def _record_result(self, result:bool, **state):
        self._data[self._test_counter]["passed"] = result
        for kw in state:
            self._data[self._test_counter]["state"][kw] = state[kw]

    def test(func):
        """
        Wrapper function for test methods.
        Intended for subclasses of TestSuite to track new tests
        and store their results.

        Assumes test function returns a pair (result:bool, state:dict),
        and only passes forward the result to return
        """
        @functools.wraps(func)
        def wrap(self, *args, **kwargs):
            self._init_test(func.__name__)
            result, state = func(self, *args, **kwargs)
            self._record_result(result=result, **state)
            return result
        return wrap


    @property
    def num_tests_passed(self):
        return len(list(filter(None, (data["passed"] for data in self._data))))

    @property
    def num_tests_total(self):
        return len(self._data)

    @property
    def all_tests_passed(self):
        return self.num_tests_passed == self.num_tests_total
    
    def print_results(self):
        if self.all_tests_passed:
            psuccess(f"[{self.name}] Passed")
        else:
            perror(f"[{self.name}] {self.num_tests_passed} / {self.num_tests_total} ({100*self.num_tests_passed/self.num_tests_total:.2f}%) passed")

    def get_state(self, test=None):
        if test is None:
            test = self._test_counter
        assert(self._test_counter >= test >= 0)
        return dict(self._data[test]["state"])

    def get_test_name(self, test=None):
        if test is None:
            test = self._test_counter
        assert(self._test_counter >= test >= 0)
        return self._data[test]["test_name"]

    def get_result(self, test=None):
        if test is None:
            test = self._test_counter
        assert(self._test_counter >= test >= 0)
        return self._data[test]["result"]

    @property
    def current_test(self):
        return self._test_counter

    @property
    def test_header(self):
        return f"[{self.name}] Test #{self.current_test:02d} ({self.get_test_name()}):"

    def _error(self, *args, **kwargs):
        perror(self.test_header, *args, **kwargs)

    def _success(self, *args, **kwargs):
        psuccess(self.test_header, *args, **kwargs)

class PythonExecutionTestSuite(TestSuite):

    def __repr__(self):
        return f"PythonExecutionTestSuite({self.name})"

    @TestSuite.test
    def exec(self, *lines, state=None, expected=None):
        
        state = dict(locals() if state is None else state)
        for (i, line) in enumerate(lines):
            try:
                exec(line, state)
            except Exception as e:
                self._error(f"""{type(e).__name__} occurred while processing line {i+1}:
\t{line}
Exception: {e}""")
                return False, dict(
                        type="exec-error",
                        lines=lines,
                        failed_at=i,
                        exception=Exception(e),
                        exec_state=state,
                        traceback=traceback.format_exc())
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
                return False, dict(
                        type="exec-diff",
                        lines=lines,
                        diff=diff,
                        exec_state=state)
        return True, dict(
                lines=lines,
                exec_state=state)
    
    def get_exec_state(self, test):
        """
        Fetch the state post-execution (or at the point of an exception)
        for the specified test number
        """
        return dict(self.get_state(test)["exec_state"])
    
    def inherit_exec_state(self, test, extern_state):
        """
        Passes state from execution #test to extern_state
        E.g., pass extern_state=locals() to instantiate all variables in local scope.
        """
        state = self.get_exec_state(test)
        for kw in state:
            extern_state[kw] = state[kw]




