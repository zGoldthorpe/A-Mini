"""
A-Mi writer
=============
Goldthorpe

This module takes an ampy.types.CFG program and outputs plaintext
A-Mi source code (that could, in principle, be re-read).
"""

import ampy.types
from ampy.ensuretypes import Syntax

class CFGWriter:
    """
    Class for formatting the output of a given CFG
    """
    @(Syntax(object, tabwidth=(int,None), codewidth=(int,None)) >> None)
    def __init__(self, tabwidth=None, codewidth=None):
        """
        tabwidth
            number of spaces before an instruction
            NB: set to None to be automatically-determined by CFG labels
            (default: None)
        codewidth
            character width of "instructions" field
            comments are placed after given tabwidth + codewidth characters
            NB: set to None to be automatically-determined
            (default: None)
        """
        self._default_tabwidth = tabwidth
        self._tabwidth = tabwidth
        self._autotab = tabwidth is None

        self._default_codewidth = codewidth
        self._codewidth = codewidth
        self._autocode = codewidth is None

        self._cfg = None

    @(Syntax(object) >> None)
    def _set_tabwidth(self):
        if self._cfg is None:
            return
        if not self._autotab:
            self._tabwidth = self._default_tabwidth
            return
        self._tabwidth = max(len(lbl) for lbl in self._cfg.labels) + 2
        return

    @(Syntax(object) >> None)
    def _set_codewidth(self):
        if self._cfg is None:
            return
        if not self._autocode:
            self._codewidth = self._default_codewidth
            return
        self._codewidth = 0
        for block in self._cfg:
            for I in block:
                self._codewidth = max(self._codewidth, len(repr(I)) + 1)

    @property
    @(Syntax(object) >> int)
    def tabwidth(self):
        if self._cfg is None:
            raise AttributeError("No CFG loaded; tabwidth not computed.")
        return self._tabwidth

    @property
    @(Syntax(object) >> int)
    def codewidth(self):
        if self._cfg is None:
            raise AttributeError("No CFG loaded; codewidth not computed.")
        return self._codewidth

    @property
    @(Syntax(object) >> int)
    def width(self):
        if self._cfg is None:
            raise AttributeError("No CFG loaded; width not computed.")
        return self.tabwidth + self.codewidth

    @(Syntax(object, ampy.types.CFG) >> None)
    def _load(self, cfg):
        """
        Load CFG for writing
        """
        self._cfg = cfg
        self._set_tabwidth()
        self._set_codewidth()

    @(Syntax(object, ampy.types.InstructionClass) >> {str})
    def _instruction_str(self, instruction):
        """
        Generates plaintext form of instruction to output list
        """
        yield ' '*self.tabwidth + repr(instruction)

    @(Syntax(object, ampy.types.BasicBlock) >> {str})
    def _block_str(self, block):
        """
        Generates plaintext form of each instruction of a block
        (starting with a blank line)
        """
        yield ""

        # block header
        yield (f"{block.label+':': <{self.width}}; parents: "
                + ", ".join(parent.label for parent in block.parents))

        for I in block:
            for I_str in self._instruction_str(I):
                yield I_str

    @(Syntax(object, ampy.types.CFG) >> {str})
    def generate(self, cfg):
        """
        Generates plaintext form of entire CFG
        """
        self._load(cfg)

        yield f"; entrypoint: {cfg.entrypoint.label}"

        for block in cfg:
            for block_str in self._block_str(block):
                yield block_str
