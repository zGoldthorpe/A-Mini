"""
Example analysis
==================
Goldthorpe

This simple analysis is meant to serve as a template for the current analysis
system. This analysis gives three pieces of data:

At the CFG level: you can pass a keyword argument "count=instructions" or
                  "count=blocks" to track either the number of blocks or the
                  number of instructions.
At the block level: you can pass an argument "add" or "mul" to track list of
                    indices of instructions that are adds or mults, resp.
At the instruction level: "index" indicates the index of the instruction in the block
"""

from ampy.ensuretypes import Syntax
from ampy.passmanager import BadArgumentException
from analysis.tools import Analysis

import ampy.types

class ExampleAnalysis(Analysis):
    # forward declaration
    pass

class ExampleAnalysis(ExampleAnalysis):
    """
    example(track, *, count)

    Example pass to demonstrate analysis functionality.
    Locally indexes every instruction in each block.

    track: "add" or "mul"
        for each block, track indices of adds or mults, resp.
        (default "add")

    count="blocks" or "instructions":
        counts the total number of blocks or instructions in CFG
        (default "blocks")
    """
    # every class should have a docstring

    # "example" is the ID of the pass
    # 1 is the max number of positional arguments expected
    # "count" is a keyword argument
    # note: all arguments are necessrily of string type
    @ExampleAnalysis.init("example", 1, "count")
    def __init__(self, instr_tracker="add", *, count="blocks"):
        # the wrapper ensures the number of arguments is correct
        # but the * is just to be safe (and to make it clear which arguments
        # are positional). It is strongly recommended that arguments to
        # Analysis objects are all optional.
        match instr_tracker:
            case "add":
                self.track_type = ampy.types.AddInstruction
                self.var = "add_indices"
            case "mul":
                self.track_type = ampy.types.MulInstruction
                self.var = "mul_indices"
            case _:
                raise BadArgumentException("Positional argument to ExampleAnalysis must be either \"add\" or \"mul\".")
        
        if count in ["blocks", "instructions"]:
            self.count = count
        else:
            raise BadArgumentException("Keyword argument \"count\" to ExampleAnalysis must be either \"blocks\" or \"instructions\".")


    @ExampleAnalysis.analysis
    @(Syntax(object) >> None)
    def get_info(self):
        # every Analysis must have exactly one analysis method
        # its name is unimportant, but MUST have the top wrapper

        # CFG metadata
        # note: metadata must be of string type
        if self.count == "blocks":
            self.assign("num_blocks", str(len(self.CFG)))
        else:
            self.assign("num_instructions", str(sum(len(block) for block in self.CFG)))

        # block metadata
        for block in self.CFG:
            for (i, I) in enumerate(block):
                if isinstance(I, self.track_type):
                    self.assign(block, self.var, str(i), append=True)
            # could have equivalently used
            # self.assign(block, self.var,
            #             *(str(i) for i in range(len(block))
            #             if isinstance(block[i], self.track_type)))

        # instruction metadata
        # (not combined with above iteration for the sake of showcasing)
        for block in self.CFG:
            for (i, I) in enumerate(block):
                self.assign(block, i, "index", str(i))
