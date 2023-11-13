"""
A-Mi interpreter
==================
Goldthorpe

This module simulates the execution of an A-Mi program encoded
as an ampy.types.CFG
"""

from utils.syntax import Syntax

import ampy.types

class RegDict:
    """
    Virtual register dictionary

    Maintains the values of all assigned virtual registers
    (Recall: all registers store integers)

    Also serves as a parser for integers.

    NB: RegDict does not perform any input-checking to
    verify that virtual registers have the correct form; this
    counts as syntax-checking and is expected to be handled by
    the reader.
    """
    def __init__(self):
        self._dict = {}

    @(Syntax(object, str) >> bool)
    def __contains__(self, key):
        """
        Determines if key identifies an integer constant
        or a previously-defined virtual register
        """
        try:
            # try first...
            _ = self[key]
            return True
        except KeyError:
            # ...apologise second
            return False

    @(Syntax(object) >> [iter, str])
    def __iter__(self):
        for key in self._dict:
            yield key

    @(Syntax(object, str) >> int)
    def __getitem__(self, key):
        if key in self._dict:
            return self._dict[key]
        try:
            return int(key)
        except ValueError:
            pass

        # this way, only one error is passed out of the method
        raise KeyError(f"{key} is not an integer or a defined virtual register.")

    @(Syntax(object, str, int) >> None)
    def __setitem__(self, key, value):
        self._dict[key] = value

    def __repr__(self):
        if len(self._dict) == 0:
            return "RegDict()"

        lhs = "reg"
        rhs = "value"

        maxllen = max(len(lhs), *(len(key) for key in self._dict))
        maxrlen = max(len(rhs), *(len(str(int(value)))
                                    for value in self._dict.values()))

        out = (f"{lhs: >{maxllen}} | {rhs: >{maxrlen}}\n"
                + f"{'':->{maxllen}}-+-{'':->{maxrlen}}\n"
                + '\n'.join(f"{key: >{maxllen}} = {value: >{maxrlen}}"
                        for key, value in self._dict.items()))
        
        return out

class Interpreter:

    def __init__(self):
        self._cfg = None
        self._rd = None
        self._block = None # points to current block in cfg
        self._block_i = None # current block instruction index
        self._prev_block = None

    @property
    @(Syntax(object) >> bool)
    def is_loaded(self):
        """
        Check if a CFG has been loaded
        """
        return self._cfg is not None

    @property
    @(Syntax(object) >> bool)
    def is_executing(self):
        """
        Check if interpreter has an instruction queued up for execution
        """
        return self._block is not None

    @property
    @(Syntax(object) >> int)
    def block_index(self):
        if not self.is_loaded:
            raise LoadError("Cannot fetch block index when no CFG is loaded.")
        return self._block_i

    @property
    @(Syntax(object) >> str)
    def block_label(self):
        if not self.is_loaded:
            raise LoadError("Cannot fetch block label when no CFG is loaded.")
        return self._block.label

    @property
    @(Syntax(object) >> ampy.types.InstructionClass)
    def current_instruction(self):
        if not self.is_executing:
            raise LoadError("Cannot fetch instruction when program is not executing.")
        return self._block[self._block_i]

    @(Syntax(object, ampy.types.CFG) >> None)
    def load(self, cfg):
        """
        Load CFG for execution.
        """
        self._cfg = cfg
        self._rd = RegDict()
        self._block = self._cfg.entrypoint
        self._block_i = 0
        self._prev_label = None

    @(Syntax(object) >> None)
    def reload(self):
        if self._cfg is None:
            raise LoadError("Cannot reload without loading at least once first.")

        self._block = self._cfg.entrypoint
        self._block_i = 0
        self._prev_label = None

    @(Syntax(object, ampy.types.InstructionClass) >> None)
    def execute_instruction(self, instruction):
        """
        Simulate the execution of a specified instruction
        """
        if not self.is_loaded:
            raise LoadError("CFG is not loaded.")

        if isinstance(instruction, ampy.types.MovInstruction):
            self._rd[instruction.target] = self._rd[instruction.operand]
            return
        if isinstance(instruction, ampy.types.PhiInstruction):
            for val, lbl in instruction.conds:
                if self._prev_label == lbl:
                    self._rd[instruction.target] = self._rd[val]
                    return
            raise UnknownInstructionError(f"phi cannot resolve branch from {self._prev_label}.")

        if isinstance(instruction, ampy.types.ArithInstructionClass):
            op0 = self._rd[instruction.operands[0]]
            op1 = self._rd[instruction.operands[1]]
            if isinstance(instruction, ampy.types.AddInstruction):
                res = op0 + op1
            elif isinstance(instruction, ampy.types.SubInstruction):
                res = op0 - op1
            elif isinstance(instruction, ampy.types.MulInstruction):
                res = op0 * op1
            else:
                raise UnknownInstructionError("Unspecified arithmetic instruction.")
            self._rd[instruction.target] = res
            return

        if isinstance(instruction, ampy.types.CompInstructionClass):
            op0 = self._rd[instruction.operands[0]]
            op1 = self._rd[instruction.operands[1]]
            if isinstance(instruction, ampy.types.EqInstruction):
                res = op0 == op1
            elif isinstance(instruction, ampy.types.NeqInstruction):
                res = op0 != op1
            elif isinstance(instruction, ampy.types.LtInstruction):
                res = op0 < op1
            elif isinstance(instruction, ampy.types.LeqInstruction):
                res = op0 <= op1
            else:
                raise UnknownInstructionError("Unspecified comparison instruction.")
            self._rd[instruction.target] = int(res)
            return

        if isinstance(instruction, ampy.types.BranchInstructionClass):
            self._block_i = 0
            self._prev_label = self.block_label
            if isinstance(instruction, ampy.types.ExitInstruction):
                # clear current block to indicate that program has exited
                self._block = None
            elif isinstance(instruction, ampy.types.GotoInstruction):
                self._block = self._cfg[instruction.target]
            elif isinstance(instruction, ampy.types.BranchInstruction):
                cond = self._rd[instruction.cond]
                if cond:
                    self._block = self._cfg[instruction.iftrue]
                else:
                    self._block = self._cfg[instruction.iffalse]
            else:
                raise UnknownInstructionError("Unspecified branch instruction.")
            return

        if isinstance(instruction, ampy.types.ReadInstruction):
            raise ReadInterrupt(instruction.target)

        if isinstance(instruction, ampy.types.WriteInstruction):
            raise WriteInterrupt(instruction.operand)

        if isinstance(instruction, ampy.types.BrkInstruction):
            raise BreakpointInterrupt(instruction.name)


    @(Syntax(object) >> None)
    def run_step(self):
        """
        Execute a single instruction, and advance the "program counter".

        May throw exceptions or interrupts that the main program
        is expected to handle appropriately.
        """
        if not self.is_loaded:
            raise LoadError("CFG not loaded.")
        if not self.is_executing:
            raise LoadError("Program already completed.")
        if self._block_i >= len(self._block):
            raise Exception("This should not happen")

        instruction = self._block[self._block_i]
        self._block_i += 1

        try:
            self.execute_instruction(instruction)
        except InstructionException as e:
            # provide more information to the thrown exception
            e.block = self._block
            e.instruction_index = self._block_i
            raise e

    @property
    @(Syntax(object) >> [tuple, str])
    def registers(self):
        return tuple(reg for reg in self._rd)

    @(Syntax(object, str) >> int)
    def read(self, reg):
        """
        Read value of register (or an integer constant)
        """
        if reg not in self._rd:
            raise KeyError(f"{reg} does not define a register or integer")
        return self._rd[reg]

    @(Syntax(object, str, int) >> None)
    def write(self, reg, value):
        """
        Write a value to specified register.
        NB: interpreter does not check the validity of the register name
        """
        self._rd[reg] = value


### Exceptions ###

class LoadError(Exception):
    """
    Thrown when an error occurs during the load of a CFG
    """
    def __init__(self, message=""):
        self.message = message
        super().__init__(message)

class InstructionException(Exception):
    """
    Thrown during the execution of an instruction
    """
    def __init__(self, message="", block=None, instruction_index=None):
        self.message = message
        self.block = block
        self.instruction_index = instruction_index
        super().__init__(message)

class UnknownInstructionError(InstructionException):
    pass

class ReadInterrupt(InstructionException):
    def __init__(self, register, block=None, instruction_index=None):
        self.register = register
        super().__init__(block=block, instruction_index=instruction_index)

class WriteInterrupt(InstructionException):
    def __init__(self, register, block=None, instruction_index=None):
        self.register = register
        super().__init__(block=block, instruction_index=instruction_index)

class BreakpointInterrupt(InstructionException):
    def __init__(self, name, block=None, instruction_index=None):
        self.name = name
        super().__init__(block=block, instruction_index=instruction_index)
