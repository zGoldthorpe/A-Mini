"""
Dead code elimination (naive)
===============================
Goldthorpe

This pass scans instructions for unused definitions and eliminates them.
However, the pass is inefficient, and does not eliminate as much as possible.
"""
# with a string of N unused definitions
# %1 = %0 + 1
# %2 = %1 + 1
# %3 = %2 + 1
# ...
# %N = %(N-1) + 1
# this algorithm needs to perform O(N) cycles to eliminate all of this code,
# and each cycle calls live analysis

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
    dce-naive

    Eliminates definitions of variables that are deemed not alive
    by the live analysis pass.
    """

    @DCE.init("dce-naive")
    def __init__(self, /):
        pass

    @DCE.opt_pass
    def eliminate(self):
        """
        dead code elimination pass
        """

        live = self.require(LiveAnalysis)
        changed = False
        while True:
            ampy.debug.print(self.ID, "Cycling through CFG")
            reduced = False
            for block in self.CFG:
                to_delete = []
                for i, I in enumerate(block):
                    if isinstance(I, ampy.types.DefInstructionClass):
                        if I.target in live.live_out(block, i):
                            continue
                        if isinstance(I, ampy.types.ReadInstruction):
                            # we cannot delete read instructions,
                            # even if the program never uses the input.
                            continue
                        reduced = True
                        ampy.debug.print(self.ID, f"Instruction {i} ({repr(I)}) in block {block.label} defines a dead variable.")
                        to_delete.append(i)

                for i in reversed(to_delete):
                    block._instructions.pop(i)

            if not reduced:
                break

            live.valid = False # invalidate live analysis and go again

        if changed:
            # live analysis will be valid because a valid live analysis
            # determines when this pass terminates
            return tuple(opt for opt in self.opts if opt.ID in ("ssa", "dce", "domtree", "live"))
        return self.opts
