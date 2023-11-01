"""
Example analysis
==================
Goldthorpe

This simple analysis is meant to serve as a template for the current analysis
system. This analysis gives three pieces of data:

At the CFG level: "num_blocks" counts the number of blocks in the CFG
At the block level: "adds" is a list of indices for which instructions are additions
At the instruction level: "idx" indicates the index of the instruction in the block
"""

from ampy.ensuretypes import Syntax
from analysis.tools import Analysis

import ampy.types

class ExampleAnalysis(Analysis):
    # forward declaration
    pass

class ExampleAnalysis(ExampleAnalysis):

    @(Syntax(object, ampy.types.CFG) >> None)
    def __init__(self, cfg):
        # every Analysis must define its ID
        self.ID = "example"
        self.CFG = cfg

    @ExampleAnalysis.analysis
    @(Syntax(object) >> None)
    def get_info(self):
        # every Analysis must have exactly one analysis method
        # its name is unimportant, but MUST have the top wrapper

        # CFG metadata
        # note: metadata must be of string type
        self.assign("num_blocks", str(len(self.CFG)))

        # block metadata
        for block in self.CFG:
            for (i, I) in enumerate(block):
                if isinstance(I, ampy.types.AddInstruction):
                    self.assign(block, "adds", str(i), append=True)
            # could have equivalently used
            # self.assign(block, "adds",
            #             *(str(i) for i in range(len(block))
            #             if isinstance(block[i], ampy.types.AddInstruction)))

        # instruction metadata
        # (not combined with above iteration for the sake of showcasing)
        for block in self.CFG:
            for (i, I) in enumerate(block):
                self.assign(block, i, "idx", str(i))
