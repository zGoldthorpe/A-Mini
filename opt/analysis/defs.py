"""
Definitions
=============
Goldthorpe

This pass tracks the locations of definitions for
the variables in the CFG
"""

from ampy.ensuretypes import Syntax
from opt.tools import Opt

import ampy.types

class DefAnalysis(Opt):
    # forward declaration
    pass

class DefAnalysis(DefAnalysis):
    """
    defs

    Records the definitions and uses of all variables,
    recording the result in global metadata.

    If a block defines a variable %0 multiple times, then the block
    will appear in defs/%0 multiple times as well.
    """

    @DefAnalysis.init("defs")
    def __init__(self, /):
        pass

    @DefAnalysis.opt_pass
    def find_defs(self):
        defs = {}

        for block in self.CFG:
            for (i, instr) in enumerate(block):
                # check if instruction defines a variable
                if not isinstance(instr, ampy.types.DefInstructionClass):
                    continue

                var = instr.target
                defs.setdefault(var, []).append(block.label)
                self.assign(block, var, str(i), append=True)

        # record results
        self.assign("vars", *sorted(defs.keys()))
        for var in defs:
            self.assign(var, *sorted(defs[var]))

        return self.opts
