"""
Dead code elimination
=======================
Goldthorpe

This pass scans instructions for unused definitions and eliminates them.
"""

from ampy.ensuretypes import Syntax

from opt.analysis.live import LiveAnalysis
from opt.tools import Opt

import ampy.types
import ampy.debug

class DCE(Opt):
    # forward declaration
    pass

class DCE(DCE):
    """
    dce

    Eliminates unused definitions from code.
    The pass is more effective if following an SSA pass.
    """

    @DCE.init("dce")
    def __init__(self, /):
        pass

    @DCE.opt_pass
    def eliminate(self):
        """
        dead code elimination pass
        """

        live = self.require(LiveAnalysis)
        changed = False
        for block in self.CFG:
            to_delete = []
            for i, I in enumerate(block):
                if isinstance(I, ampy.types.DefInstructionClass):
                    if I.target in live[block:i:"out"]:
                        continue
                    if isinstance(I, ampy.types.ReadInstruction):
                        # we cannot delete read instructions,
                        # even if the program never uses the input.
                        continue
                    changed = True
                    ampy.debug.print(self.ID, f"Instruction {i} ({repr(I)}) in block {block.label} defines a dead variable.")
                    to_delete.append(i)

            for i in reversed(to_delete):
                block._instructions.pop(i)

        if changed:
            return tuple(opt for opt in self.opts if opt.ID in ("ssa", "dce", "domtree"))
        return self.opts
