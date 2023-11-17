"""
Example opt
==================
Goldthorpe

This simple opt is meant to serve as a template for the current opt
system. This opt gives three pieces of data:

At the CFG level: you can pass a keyword argument "count=instructions" or
                  "count=blocks" to track either the number of blocks or the
                  number of instructions.
At the block level: you can pass an argument "add" or "mul" to track list of
                    indices of instructions that are adds or mults, resp.
At the instruction level: "index" indicates the index of the instruction in the block
"""

from utils.syntax import Syntax

from opt.tools import Opt, RequiresOpt

from ampy.passmanager import BadArgumentException
import ampy.types

class ExampleAnalysis(Opt):
    # forward declaration
    pass

class ExampleAnalysis(ExampleAnalysis):
    """
    Example analysis pass to demonstrate some opt functionality.
    Locally indexes every instruction in each block.

    instr_tracker: "add" or "mul"
        for each block, track indices of adds or mults, resp.

    count="blocks" or "instructions":
        counts the total number of blocks or instructions in CFG
    """
    # every class should have a docstring

    # "example_analysis" is the ID of the pass
    # "add" is the default value for the positional argument
    # count="blocks" is the default value for the keywoard argument
    # note: all arguments are necessrily of string type
    @ExampleAnalysis.init("example_analysis", "add", count="blocks")
    def __init__(self, instr_tracker, *, count):
        # the * indicates where the keyword arguments start
        # note that default arguments are not passed here since they
        # are handled by the wrapper

        match instr_tracker:
            case "add":
                self.track_type = ampy.types.AddInstruction
                self.var = "add_indices"
            case "mul":
                self.track_type = ampy.types.MulInstruction
                self.var = "mul_indices"
            case _:
                raise BadArgumentException("Positional argument of ExampleAnalysis must be either \"add\" or \"mul\".")
        
        if count in ["blocks", "instructions"]:
            self.count = count
        else:
            raise BadArgumentException("Keyword argument \"count\" of ExampleAnalysis must be either \"blocks\" or \"instructions\".")


    @ExampleAnalysis.opt_pass
    def get_info(self):
        """
        Scans the CFG for the number of blocks or instructions,
        tracks the additions or multiplications,
        and locally indexes the instructions.
        """
        # every Opt must have exactly one opt method
        # its name is unimportant, but MUST be decorated as above.

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

        # since this is an analysis pass, it does not affect the CFG
        # therefore, return all opts as "preserved"
        return self.opts

    @ExampleAnalysis.getter
    @(Syntax(object) >> int)
    def get_count(self):
        """
        Fetch the number of blocks or instructions
        """
        return int(self[f"num_{self.count}"])

    @ExampleAnalysis.getter
    @(Syntax(object, ampy.types.BasicBlock) >> [int])
    def get_op_indices(self, block):
        """
        Return the list of instruction indices of the adds or multiplications
        in the given block
        """
        return list(map(int, self[block:self.var]))

class AddLister(RequiresOpt):
    """
    This is an example of a class that interprets data from an opt,
    which may be convenient for other opts or optimisations
    """

    @(Syntax(object, str) >> [list, ampy.types.InstructionClass])
    def list_adds(self, block_label):
        if block_label not in self.CFG.labels:
            return []
        block = self.CFG[block_label]
        outs = []
        for i_str in self.require(ExampleAnalysis, "add", count=any)[block:"add_indices"]:
            # if the example opt does not run with the argument "add", then it will trigger
            # processing of the specified example opt
            i = int(i_str)
            outs.append(block[i])
        return outs
