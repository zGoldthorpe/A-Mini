"""
A-Mi reader
=============
Goldthorpe

This module provides the CFGBuilder, which takes A-Mi code
(written in a plaintext file) and yields an ampy.types.CFG abstraction
for analysis or interpretation.
"""

import ampy.types
from ampy.ensuretypes import Syntax

import re


### Operation parsing ###

class OperationReader:
    """
    Operation class for syntax parsing
    """
    @(Syntax(object, str, type, extract=lambda:Syntax(re.Match)>>tuple) >> None)
    def __init__(self, syntax_re, instr_cls, extract=lambda m: m.groups()):
        """
        syntax_re = regex for instruction (with grouping)
        instr_cls = InstructionClass subclass to match
        extract = function that takes a re.Match object and returns a tuple
        of arguments to pass to the instr_cls constructor.
        """
        self._syntax = re.compile(syntax_re.replace(' ',r"\s*"))
        self._repr = syntax_re
        self._cls = instr_cls
        self._extract = extract

    def __repr__(self):
        return f"Op({self._repr})"

    @(Syntax(object, str) >> (ampy.types.InstructionClass, None))
    def read(self, instruction):
        """
        Try to match the instruction string to our regex syntax.
        If match fails, returns None
        Otherwise, returns the instruction class instance produced
        from parsing.
        """
        m = self._syntax.fullmatch(_clean_whitespace(instruction))
        if m is None:
            return None
        return self._cls(*self._extract(m))


### Regular expressions ###

_id  = r"[.\w]+"
_num = r"-?\d+"
_reg = rf"%{_id}"
_ron = rf"(?:{_reg}|{_num})"
_tgt = rf"@{_id}"
_var = rf"({_reg})"
_op  = rf"({_ron})"
_lbl = rf"({_tgt})"

### Parsing information ###

# Phi parsing
_phi_conds = re.compile(rf"\[\s*{_op}\s*,\s*{_lbl}\s*\]")
def _extract_phi_args(m:re.Match):
    """
    Takes a match object for the PhiInstruction
    
    {_var} = phi ((?:\[ (?:{_ron}) , (?:{_tgt}) \] ,? )+)"

    and returns the tuple of arguments for a PhiInstruction

    @Syntax(object, str, [str, 2], ...)
    """
    lhs = m.group(1)
    conds = [(cond.group(1), cond.group(2))
            for cond in _phi_conds.finditer(m.group(2))]

    return lhs, *conds

# All valid operations
_opcodes = dict(
        # moves
        mov = OperationReader(
            rf"{_var} = {_op}",
            ampy.types.MovInstruction,
            ),
        phi = OperationReader(
            rf"{_var} = phi ((?:\[ (?:{_ron}) , (?:{_tgt}) \] ,? )+)",
            ampy.types.PhiInstruction,
            extract=_extract_phi_args,
            ),
        # arithmetic
        add = OperationReader(
            rf"{_var} = {_op} \+ {_op}",
            ampy.types.AddInstruction,
            ),
        sub = OperationReader(
            rf"{_var} = {_op} - {_op}",
            ampy.types.SubInstruction,
            ),
        mul = OperationReader(
            rf"{_var} = {_op} \* {_op}",
            ampy.types.MulInstruction,
            ),
        # comparisons
        eq  = OperationReader(
            rf"{_var} = {_op} == {_op}",
            ampy.types.EqInstruction,
            ),
        neq = OperationReader(
            rf"{_var} = {_op} != {_op}",
            ampy.types.NeqInstruction,
            ),
        lt  = OperationReader(
            rf"{_var} = {_op} < {_op}",
            ampy.types.LtInstruction,
            ),
        leq = OperationReader(
            rf"{_var} = {_op} <= {_op}",
            ampy.types.LeqInstruction,
            ),
        # branching
        goto = OperationReader(
            rf"goto {_lbl}",
            ampy.types.GotoInstruction,
            ),
        branch = OperationReader(
            rf"branch {_op} \? {_lbl} : {_lbl}",
            ampy.types.BranchInstruction,
            ),
        exit = OperationReader(
            rf"exit",
            ampy.types.ExitInstruction,
            ),
        # I/O
        read = OperationReader(
            rf"read {_var}",
            ampy.types.ReadInstruction,
            ),
        write = OperationReader(
            rf"write {_op}",
            ampy.types.WriteInstruction,
            ),
        # debugging
        brkpt = OperationReader(
            rf"brkpt !({_id})",
            ampy.types.BrkInstruction,
            ),
        )


### CFG constructor ###

class CFGBuilder:
    """
    Factory for constructing control flow graphs
    """
    @(Syntax(object, allow_anon_blocks=bool, entrypoint_label=(str,None)) >> None)
    def __init__(self, allow_anon_blocks=True, entrypoint_label=None):
        """
        The allow_anon_blocks flag toggles whether or not basic blocks are
        all required to be labelled
        """
        self.allow_anon_blocks = allow_anon_blocks
        self._entrypoint_label = entrypoint_label

    @(Syntax(object, str, ...) >> ampy.types.CFG)
    def build(self, *instructions):
        """
        Given a list of instructions (each line being a valid line of
        A/Mi code), returns an ampy.types.CFG for the program.

        Assumes first basic block in code is the entrypoint, unless it
        finds a block with label given by self._entrypoint_label
        """
        self._current_block = []
        # list of instructions in current basic block
        self._block_label = None
        # label string of current block
        self._entrypoint = None
        # label string of entrypoint block

        self._fallthrough_parent = None
        # if current block comes from fallthrough (previous instruction
        # is a branch), then this stores ampy.types.BasicBlock of parent
        self._anon = 0
        # counter for anonymous block labels
        # besides first block, I don't think it's possible to create
        # anonymous blocks that don't consist of dead code, but if the
        # instruction after a branch is not labelled, then this is necessary
        # (alternatively, the language syntax could be more strict)

        self._block_start = 0
        # tracks the line of the block being built

        cfg = ampy.types.CFG()
        for (i, instruction) in enumerate(instructions):
            if ';' in instruction:
                # ignore comment
                instruction, _ = instruction.split(';', 1)
            
            if instruction.startswith('@') and ':' in instruction:
                # new label; possible fallthrough
                # (unless self._block_label is None or self._current_block is nonempty)
                self._commit_block(cfg, fallthrough=True)
                self._block_start = i
                self._block_label, instruction = instruction.split(':', 1)

            instruction = instruction.strip() # strip whitespace
            if len(instruction) == 0:
                # empty instruction
                continue
            
            decoded = None
            for op in _opcodes:
                # try decoding with each opcode
                decoded = _opcodes[op].read(instruction)
                if decoded is not None:
                    break
            if decoded is None:
                raise ParseError(i, f"Unrecognised instruction \"{instruction}\"")

            self._current_block.append(decoded)
            
            if isinstance(decoded, ampy.types.BranchInstructionClass):
                # branch means the end of a basic block
                self._commit_block(cfg)
                self._block_start = i + 1

        # all instructions have been parsed
        # but unless an exit instruction is explicitly called
        # there may still be a block to commit
        self._commit_block(cfg)

        if self._entrypoint is None:
            raise EmptyCFGError

        # finally, assert entrypoint
        cfg.set_entrypoint(self._entrypoint)
        if self._entrypoint_label is not None and cfg.entrypoint.label != self._entrypoint_label:
            raise NoEntryPointError(len(instructions), f"Entrypoint {self._entrypoint_label} does not exist in program")


        # Now, CFG should be completed
        cfg.assert_completeness()
        return cfg

    @(Syntax(object, ampy.types.CFG, fallthrough=bool) >> None)
    def _commit_block(self, cfg, fallthrough=False):
        """
        Pushes the block built so far into the cfg, unless both the label
        is None and the current block is empty.
        """
        if self._block_label is None:
            if len(self._current_block) == 0:
                # there is no block to commit
                return
            # otherwise, this is an anonymous block
            if not self.allow_anon_blocks:
                raise AnonymousBlockError(self._block_start)
            self._block_label = f"@.__{self._anon}"
            self._anon += 1

        if self._block_label == self._entrypoint_label:
            # explicit entrypoint was found!
            self._entrypoint = self._entrypoint_label

        if self._entrypoint is None:
            self._entrypoint = self._block_label
            # tentatively assume first block label is entrypoint
        
        cfg.add_block(self._block_label, *self._current_block)
        block = cfg[self._block_label]

        # handle fallthroughs
        if self._fallthrough_parent is not None:
            self._fallthrough_parent.add_child(block)
            self._fallthrough_parent = None
        if fallthrough:
            self._fallthrough_parent = block

        # now, create new current block
        self._current_block = []
        self._block_label = None


### Exceptions ###

class ParseError(Exception):

    def __init__(self, line, message=""):
        self.message = message
        self.line = line
        super().__init__(message)

class NoEntryPointError(ParseError):
    pass

class AnonymousBlockError(ParseError):
    pass

class EmptyCFGError(ParseError):
    def __init__(self, message=""):
        super().__init__(-1, message=message)

### Private helper methods ###

def _clean_whitespace(instr):
    """
    Cleans up instruction whitespace
    """
    return ' '.join(instr.strip().split())

