"""
Phi elimination
=================
Goldthorpe

Simple phi-node elimination pass.
Hoists definitions to parent blocks as move instructions, and
then converts phi instruction into another move instruction.
"""

from utils.syntax import Syntax

from opt.tools import Opt
from opt.analysis.defs import DefAnalysis

import ampy.types

class PhiElim(Opt):
    # forward declaration
    pass

class PhiElim(PhiElim):
    """
    Simple phi-elimination pass; doesn't do anything fancy.
    """

    @PhiElim.init("phi-elim")
    def __init__(self, /):
        pass

    @PhiElim.opt_pass
    def eliminate(self):
        """
        Phi-elimination
        """
        changed = False
        for block in self.CFG:
            for i, I in enumerate(block):
                if not isinstance(I, ampy.types.PhiInstruction):
                    continue
                changed = True
                reg = self._new_phi_reg(I.target)

                for val, lbl in I.conds:
                    # move value to target in parent block
                    self.CFG[lbl]._instructions.insert(-1,
                            ampy.types.MovInstruction(reg, val))

                block._instructions[i] = ampy.types.MovInstruction(I.target, reg)

        if changed:
            return tuple(opt for opt in self.opts if opt.ID in ("phi-elim", "domtree"))
        return self.opts

    @(Syntax(object, str) >> str)
    def _new_phi_reg(self, var):
        """
        Generates a new phi register name, based on the provided one.
        """
        ret = var + ".phi"
        defs = self.require(DefAnalysis)
        idx = -1
        while ret in defs.vars:
            idx += 1
            ret = f"{var}.phi.{idx}"
        return ret
