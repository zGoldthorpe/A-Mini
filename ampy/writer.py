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
    @(Syntax(object, write_meta=bool, tabwidth=(int,None), codewidth=(int,None)) >> None)
    def __init__(self, write_meta=True, tabwidth=None, codewidth=None):
        """
        write_meta
            toggle if metadata should be written to output
        tabwidth
            number of spaces before an instruction
            NB: set to None to be automatically-determined by CFG labels
            (default: None)
        codewidth
            character width of "instructions" field
            comments are placed after given tabwidth + codewidth characters
            NB: set to None to be automatically-determined
            (default: None)
        Blocks are written in reverse post-order
        """
        self._write_meta = write_meta

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
    @(Syntax(object) >> bool)
    def write_meta(self):
        return self._write_meta

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

    @(Syntax(object, str, str, [str]) >> [iter, str])
    def _meta_str(self, char, key, values):
        """
        Generates metadata comment.

        char
            one of "#@%" to indicate level
        key, values
            the metadata to write

        Could be multi-line because of the presence of "$" value
        """
        start = 0
        end = -1
        if values is not None:
            while end < len(values):
                try:
                    end = values.index('$', start) + 1
                except ValueError: # no '$' to be found
                    end = len(values)
                
                yield f";{char}!{key}: " + ' '.join(values[start:end])
                start = end

    @(Syntax(object, ampy.types.InstructionClass) >> [iter, str])
    def _instruction_str(self, instruction):
        """
        Generates plaintext form of instruction to output list
        """
        tab = ' '*self.tabwidth
        instr = f"{repr(instruction): <{self.codewidth}}"
        line = tab + instr
        if not self.write_meta or len(instruction.meta) == 0:
            yield line
        else:
            for var, val in sorted(instruction.meta.items(), key=lambda t:t[0]):
                for metadata in self._meta_str('%', var, val):
                    yield line + metadata
                    line = ' '*self.width
                line = ' '*self.width

    @(Syntax(object, ampy.types.BasicBlock) >> [iter, str])
    def _block_str(self, block):
        """
        Generates plaintext form of each instruction of a block
        (starting with a blank line)
        """
        yield ""
        line = f"{block.label+':': <{self.width}}"
        if not self.write_meta or len(block.meta) == 0:
            yield line
        else:
            for var, val in sorted(block.meta.items(), key=lambda t:t[0]):
                for metadata in self._meta_str('@', var, val):
                    yield line + metadata
                    line = ' '*self.width
                line = ' '*self.width

        for I in block:
            for I_str in self._instruction_str(I):
                yield I_str

    @(Syntax(object, ampy.types.CFG) >> [iter, ampy.types.BasicBlock])
    def _traverse_rpo(self, cfg):
        """
        Generate blocks of CFG in RPO

        Note: unreachable blocks are automatically eliminated
        """
        seen = set()
        postorder = []
        
        def dfs(block):
            seen.add(block)
            for child in block.children:
                if child not in seen:
                    dfs(child)
            postorder.append(block)

        dfs(cfg.entrypoint)

        for block in reversed(postorder):
            yield block

    @(Syntax(object, ampy.types.CFG) >> [iter, str])
    def generate(self, cfg):
        """
        Generates plaintext form of entire CFG
        """
        self._load(cfg)

        if self.write_meta:
            for var, val in sorted(cfg.meta.items(), key=lambda t:t[0]):
                for metadata in self._meta_str('#', var, val):
                    yield metadata

        for block in self._traverse_rpo(cfg):
            for block_str in self._block_str(block):
                yield block_str
