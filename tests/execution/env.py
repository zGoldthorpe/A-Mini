"""
Execution environment simulator
=================================
Goldthorpe

Provides a testing.tools.TestSuite subclass specific
for simulating execution with the ampy.interpret.Interpreter

Relies on the correctness of ampy.reader.CFGBuilder
"""
from collections import deque
import traceback

from tests.tools import TestSuite
from ampy.printing import tame_whitespace as tw

import ampy.interpret
import ampy.reader

class ExecutionTestSuite(TestSuite):
    
    def __init__(self, name, read_handler=lambda e:0, write_handler=lambda v,e:None, brk_handler=lambda n,e:None):
        """
        Initialiser for execution test suite.

        read_handler:
            takes an ampy.interpret.ReadInterrupt object and returns an integer
        write_handler:
            takes an integer and an ampy.interpret.WriteInterrupt object, and returns nothing
        brk_handler:
            takes an ampy.interpret.BreakpointInterrupt object and a dictionary, and returns nothing
        """
        self._interpreter = ampy.interpret.Interpreter()
        self._read = read_handler
        self._write = write_handler
        self._brk = brk_handler
        super().__init__(name)

    def __repr__(self):
        return f"ExecutionTestSuite({self.name})"

    @property
    def register_dict(self):
        return {reg:self._interpreter.read(reg)
                for reg in self._interpreter.registers}

    def set_read_handler(read_handler):
        self._read = read_handler

    def set_write_handler(write_handler):
        self._write = write_handler

    def set_brk_handler(brk_handler):
        self._brk = brk_handler

    def call_read(self, e:ampy.interpret.ReadInterrupt):
        self._interpreter.write(e.register, self._read(e))

    def call_write(self, e:ampy.interpret.WriteInterrupt):
        self._write(self._interpreter.read(e.register), e)
    
    def call_breakpoint(self, e:ampy.interpret.BreakpointInterrupt):
        self._brk(e, self.register_dict)
    
    @TestSuite.test
    def simulate(self, *instructions, expected=dict(), onexit="", onexitlocals=None):
        """
        Simulates the list of instructions (given as strings).

        Then tests that the registers specified in the provided
        dict match their expected values.

        onexit is (python) script that should execute without error
        on the completion of the simulation.
        """
        # build CFG
        try:
            cfg = ampy.reader.CFGBuilder().build(*instructions)
        except Exception as e:
            self._error(tw(f"""
                Unexpected {type(e).__name__} occurred while building CFG.
                Exception: {e}"""))
            return False, dict(
                    type="build",
                    instructions=instructions,
                    exception=Exception(e),
                    traceback=traceback.format_exc())

        # load CFG to interpreter
        try:
            self._interpreter.load(cfg)
        except Exception as e:
            self._error(tw(f"""
                Unexpected {type(e).__name__} occurred while loading CFG.
                Exception: {e}"""))
            return False, dict(
                    type="load",
                    instructions=instructions,
                    cfg=cfg,
                    exception=Exception(e),
                    traceback=traceback.format_exc())

        # run interpreter
        while self._interpreter.is_executing:
            try:
                self._interpreter.run_step()
            except ampy.interpret.ReadInterrupt as e:
                self.call_read(e)
            except ampy.interpret.WriteInterrupt as e:
                self.call_write(e)
            except ampy.interpret.BreakpointInterrupt as e:
                self.call_breakpoint(e)
            except Exception as e:
                self._error(tw(f"""
                    Unexpected {type(e).__name__} occurred while reading instruction {self._interpreter.block_index}:
                        {repr(self._interpreter.current_instruction)}
                    Exception: {e}"""))
                return False, dict(
                        type="runtime",
                        instructions=instructions,
                        label=self._interpreter.block_label,
                        index=self._interpreter.block_index,
                        exception=Exception(e),
                        registers=self.register_dict,
                        traceback=traceback.format_exc())

        # test outcome of execution
        for reg in expected:
            try:
                assert expected[reg] == self._interpreter.read(reg)
            except IndexError:
                self._error(f"{reg} not defined after execution (expected {expected[reg]}).")
                return False, dict(
                        type="undef",
                        instructions=instructions,
                        register=reg,
                        expected=expected[reg])
            except AssertionError:
                self._error(f"Computation ends with {reg} = {self._interpreter.read(reg)} (expected {expected[reg]}).")
                return False, dict(
                        type="mismatch",
                        instructions=instructions,
                        register=reg,
                        expected=expected[reg],
                        received=self._interpreter.read(reg))

        # final tests
        try:
            exec(onexit, onexitlocals)
        except Exception as e:
            self._error(f"Execution of\n{onexit}\nresulted in an {type(e).__name__}\nException: {e}")
            return False, dict(
                        type="on-exit",
                        onexit=onexit,
                        exception=Exception(e))

        return True, dict(instructions=instructions,
            registers=self.register_dict)


class InputSimulator(deque):
    """
    Simulates input (for an ExecutionTestSuite instance).

    Pushed inputs will be popped once per query (FIFO)
    """
    def push_input(self, *inputs):
        for i in inputs:
            self.appendleft(i)

    def __call__(self, _):
        return self.pop()

class OutputTester(deque):
    """
    Fetches output and tests against expectation
    """
    def push_output(self, *outputs):
        for o in outputs:
            self.appendleft(o)

    def __call__(self, output, _):
        assert int(output) == self.pop()

class BreakpointTester(deque):
    """
    Intersects breakpoint interrupts and tests them.
    """
    def push_brk(name, state:dict):
        self.appendleft((name, state))

    def __call__(self, e, state):
        name, expected = self.pop()
        assert name == e.name
        for key in expected:
            assert key in state and expected[key] == state[key]
