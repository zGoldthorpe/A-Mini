"""
Definitions
=============
Goldthorpe

This pass tracks the locations of definitions for
the variables in the CFG
"""

from ampy.ensuretypes import Syntax
from analysis.tools import Analysis

import ampy.types

class DefAnalysis(Analysis):
    # forward declaration
    pass

class DefAnalysis(DefAnalysis):
    """
    defs

    Records the definitions and uses of all variables,
    recording the result in global metadata.

    Repeated definitions in a block will lead to repeated
    appearances of the block label in list of variable
    definition locations.
    """

    @DefAnalysis.init("defs")
    def __init__(self, /):
        pass

    @DefAnalysis.analysis
    def find_defs(self):
        defs = {}

        for block in self.CFG:
            for (i, instr) in enumerate(block):
                # check if instruction defines a variable
                if not isinstance(instr, (
                        ampy.types.ArithInstructionClass,
                        ampy.types.CompInstructionClass,
                        ampy.types.MovInstruction,
                        ampy.types.PhiInstruction,
                        ampy.types.ReadInstruction)):
                    continue

                var = instr.target
                defs.setdefault(var, set()).add(block.label)
                self.assign(block, var, str(i), append=True)

        # record results
        self.assign("vars", *sorted(defs.keys()))
        for var in defs:
            self.assign(var, *sorted(defs[var]))
