import ampy.types

import re

### Regular expressions ###
_id  =  r"[.\w]+"
_num = r"-?\d+"
_reg = rf"%{_id}"
_ron = rf"(?:{_reg}|{_num})"
_tgt = rf"@{_id}"
_var = rf"({_reg})"
_op  = rf"({_ron})"
_lbl = rf"({_tgt})"

### Operation parsing ###

class OperationReader:
    """
    Operation class for syntax parsing
    """
    def __init__(self, syntax_re, instr_cls):
        self.syntax = re.compile(syntax_re.replace(' ',r"\s*"))
        self.repr = syntax_re
        self.cls = instr_cls

    def __repr__(self):
        return f"Op({self.repr})"

    def read(self, instruction):
        m = self.syntax.fullmatch(_clean_whitespace(instruction))
        if m is None:
            return None
        return self.cls(*m.groups())

### Operation syntax rules ###

_opcodes = dict(
        # moves
        mov = OperationReader(
            rf"{_var} = {_op}",
            ampy.types.MovInstruction,
            ),
        phi = OperationReader(
            rf"{_var} = phi ((?:\[ {_ron} , {_tgt} \] ,?)+)",
            ampy.types.PhiInstruction,
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
            ampy.types.BrancInstruction,
            ),
        # I/O
        read = OperationReader(
            rf"read {_var}",
            ampy.types.ReadInstruction,
            ),
        write = OperationReader(
            rf"write {_var}",
            ampy.types.WriteInstruction,
            ),
        # debugging
        brkpt = OperationReader(
            rf"brkpt !({_id})",
            ampy.types.BrkInstruction,
            ),
        )

### CFG construction ###
#TODO: port CFGBuilder from ampy.parser

### Private helper methods ###

def _clean_whitespace(instr):
    """
    Cleans up instruction whitespace
    """
    return ' '.join(instr.strip().split())

