"""
A-Mi reader
=============
Goldthorpe

This module provides the CFGBuilder, which takes A-Mi code
(written in a plaintext file) and yields an ampy.types.CFG abstraction
for analysis or interpretation.
"""

import re

from utils.syntax import Syntax

import ampy.types


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
        m = self._syntax.fullmatch(_preprocess(instruction))
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

_meta = r"([^:\s]+)"

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
        neg = OperationReader(
            rf"{_var} = - {_op}",
            ampy.types.NegInstruction, # phony
            ),
        mul = OperationReader(
            rf"{_var} = {_op} \* {_op}",
            ampy.types.MulInstruction,
            ),
        div = OperationReader(
            rf"{_var} = {_op} / {_op}",
            ampy.types.DivInstruction,
            ),
        mod = OperationReader(
            rf"{_var} = {_op} % {_op}",
            ampy.types.ModInstruction,
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
        gt  = OperationReader(
            rf"{_var} = {_op} > {_op}",
            ampy.types.GtInstruction,
            ),
        leq = OperationReader(
            rf"{_var} = {_op} <= {_op}",
            ampy.types.LeqInstruction,
            ),
        geq = OperationReader(
            rf"{_var} = {_op} >= {_op}",
            ampy.types.GeqInstruction,
            ),
        # bitwise
        land = OperationReader(
            rf"{_var} = {_op} & {_op}",
            ampy.types.AndInstruction,
            ),
        lor = OperationReader(
            rf"{_var} = {_op} | {_op}",
            ampy.types.OrInstruction,
            ),
        xor = OperationReader(
            rf"{_var} = {_op} \^ {_op}",
            ampy.types.XOrInstruction,
            ),
        lnot = OperationReader(
            rf"{_var} = ~{_op}",
            ampy.types.NotInstruction,
            ),
        lshift = OperationReader(
            rf"{_var} = {_op} << {_op}",
            ampy.types.LShiftInstruction,
            ),
        rshift = OperationReader(
            rf"{_var} = {_op} >> {_op}",
            ampy.types.RShiftInstruction,
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
        self._meta = {}
        # tracks metadata for CFG
        self._current_block = []
        # list of instructions in current basic block
        self._block_meta = {}
        # tracks metadata of current block being built
        self._block_label = None
        # label string of current block
        self._entrypoint = None
        # label string of entrypoint block

        self._fallthrough_parent = None
        # if current block comes from fallthrough (previous instruction
        # is not a branch), then this stores ampy.types.BasicBlock of parent

        self._block_start = 0
        # tracks the line of the block being built

        self._last_instruction = None
        # tracks the previous decoded instruction, in case we append metadata

        cfg = ampy.types.CFG()
        for (i, instruction) in enumerate(instructions):
            if ';' in instruction:
                # ignore comment
                instruction, comment = instruction.split(';', 1)
                comment = comment.strip()
            else:
                comment = ""
            
            if instruction.startswith('@') and ':' in instruction:
                # new label; possible fallthrough
                # (unless self._block_label is None or self._current_block is nonempty)
                self._commit_block(cfg, fallthrough=True)
                self._block_start = i
                self._last_instruction = None
                self._block_label, instruction = instruction.split(':', 1)
                if re.fullmatch(_lbl, self._block_label) is None:
                    raise ParseError(i, f"Invalid label \"{self._block_label}\".")

            instruction = instruction.strip() # strip whitespace

            # process comment for metadata
            prog_arg = re.fullmatch(rf"#!{_meta}:(.*)", comment)
            block_arg = re.fullmatch(rf"@!{_meta}:(.*)", comment)
            instr_arg = re.fullmatch(rf"%!{_meta}:(.*)", comment)
            if prog_arg is not None:
                cfg.meta.setdefault(prog_arg.group(1), []
                        ).extend(prog_arg.group(2).split())
            elif block_arg is not None:
                self._block_meta.setdefault(block_arg.group(1), []
                        ).extend(block_arg.group(2).split())


            if len(instruction) != 0:
                decoded = None
                for op in _opcodes:
                    # try decoding with each opcode
                    decoded = _opcodes[op].read(instruction)
                    if decoded is not None:
                        break
                if decoded is None:
                    raise ParseError(i, f"Unrecognised instruction \"{instruction}\"")

                self._current_block.append(decoded)
                self._last_instruction = decoded
            
                if isinstance(decoded, ampy.types.BranchInstructionClass):
                    # branch means the end of a basic block
                    self._commit_block(cfg)
                    self._block_start = i + 1


            if instr_arg is not None and self._last_instruction is not None:
                self._last_instruction.meta.setdefault(
                        instr_arg.group(1), []).extend(instr_arg.group(2).split())

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
        cfg.tidy()
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
            raise AnonymousBlockError(self._block_start)

        if self._block_label == self._entrypoint_label:
            # explicit entrypoint was found!
            self._entrypoint = self._entrypoint_label

        if self._entrypoint is None:
            self._entrypoint = self._block_label
            # tentatively assume first block label is entrypoint
        
        cfg.add_block(self._block_label, *self._current_block)
        block = cfg[self._block_label]

        # add and reset metadata
        block.meta = self._block_meta
        self._block_meta = {}

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

def _preprocess(instr):
    """
    Cleans up instruction
    """
    instr = re.sub(r"\s+", ' ', instr)
    instr = re.sub(r"(\W)(-?0x[0-9a-fA-F]+)", # convert hex
            lambda m: m.group(1) + str(int(m.group(2), base=16)), instr)
    return ' '.join(instr.strip().split())

