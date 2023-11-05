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
from analysis.tools import Analysis, RequiresAnalysis

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
    # "add" is the default argument for the positional argument
    # count="blocks" is the default argument for the keywoard argument
    # note: all arguments are necessrily of string type
    @ExampleAnalysis.init("example", "add", count="blocks")
    def __init__(self, instr_tracker, *, count):
        # the * indicates where the keyword arguments start
        # note that default arguments are not passed since they are handled
        # by the wrapper

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
            self.assign(block, self.var)
            # it is important to clear the variable before appending
            # in case a previously invalidated pass still has data stored
            for (i, I) in enumerate(block):
                if isinstance(I, self.track_type):
                    self.assign(block, self.var, str(i), append=True)
            # we could have equivalently used
            # self.assign(block, self.var,
            #             *(str(i) for i in range(len(block))
            #             if isinstance(block[i], self.track_type)))
            # in which case clearing the variable is unnecessary
            # (because we are not appending)

        # instruction metadata
        # (not combined with above iteration for the sake of showcasing)
        for block in self.CFG:
            for (i, I) in enumerate(block):
                self.assign(block, i, "index", str(i))

class AddLister(RequiresAnalysis):
    """
    This is an example of a class that interprets data from an analysis,
    which may be convenient for other analyses or optimisations
    """

    @(Syntax(object, str) >> [list, ampy.types.InstructionClass])
    def list_adds(self, block_label):
        if block_label not in self.CFG.labels:
            return []
        block = self.CFG[block_label]
        outs = []
        for i_str in self.require_analysis(ExampleAnalysis, "add", count=any)[block:"add_indices"]:
            # if the example analysis does not run with the argument "add", then it will trigger
            # processing of the specified example analysis
            i = int(i_str)
            outs.append(block[i])
        return outs
