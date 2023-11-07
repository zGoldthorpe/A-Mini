"""
Example optimisation
======================
Goldthorpe

This simple "optimisation" is meant to serve as a template for the current
optimisation system.

The first positional argument can be "add" or "mul", and the pass
will swap the operands of all addition or multiplication instructions.

You can also pass a keyword argument "max_block_size", and the pass
will add goto instructions to break up the
code into blocks of specified maximum size.
(Or pass -1 to avoid trimming block size.)
"""
from ampy.ensuretypes import Syntax
from ampy.passmanager import BadArgumentException
from opt.tools import Opt

import ampy.types

### required analyses ###
from analysis.example import ExampleAnalysis

class ExampleOpt(Opt):
    # forward declaration
    pass

class ExampleOpt(ExampleOpt):
    """
    example_opt(swap, *, max_block_size)

    Example pass to demonstrate optimisation functionality.
    
    swap: "add" or "mul"
        for each add or mul instruction, swap the operands.
        (default "add")

    max_block_size=int:
        if -1, does nothing; otherwise, cuts blocks into
        chunks of specified maximum size
        (default -1)
    """
    # every class should have a docstring

    # "example_opt" is the ID of the pass
    # "add" is the default value for the positional argument
    # count="-1" is the default value for the keyword argument
    # note: all arguments are necessarily of string type
    @ExampleOpt.init("example_opt", "add", max_block_size="-1")
    def __init__(self, swap, *, max_block_size):
        # the * indicates where the keyword arguments start
        # note that default arguments are not passed here since they
        # are handled by the wrapper

        if swap not in ("add", "mul"):
            raise BadArgumentException("Positional argument of ExampleOpt must be either \"add\" or \"mul\".")

        self.swap = swap

        try:
            self.max_size = int(max_block_size)
        except ValueError:
            raise BadArgumentException("Keyword argument \"max_block_size\" of ExampleOpt must be an integer.")
        
        if self.max_size < 2 and self.max_size != -1:
            raise BadArgumentException("Keyword argument \"max_block_size\" of ExampleOpt must be at least 2, or equal to -1.")

    @ExampleOpt.opt
    def swap_and_trim(self):
        """
        Swap operands of either additions or multiplications, and trims
        basic blocks down to size.
        """
        # every Opt must have exactly one opt method
        # its name is unimportant, but MUST be decorated as above.
        
        for block in list(self.CFG):
            swaps = self.require_analysis(ExampleAnalysis, self.swap, count=any)[block:f"{self.swap}_indices"]
            # fetch results from the example analysis (can also omit the count kwarg)
            for i_str in swaps:
                i = int(i_str)
                (op1, op2) = block[i].operands
                block[i].operands = (op2, op1)

        preserved = tuple(analysis for analysis in self.analyses
                        if isinstance(analysis, ExampleAnalysis))

        if self.max_size != -1:
            # time to trim basic blocks
            changed = False
            blocks = tuple(self.CFG)
            # pass blocks to tuple because CFG
            # is going to undergo changes
            for block in blocks:
                if len(block) <= self.max_size:
                    continue
                changed = True

                num_instrs = len(block)
                new_block_count = num_instrs // (self.max_size-1) + 1
                # safe to overshoot this count
                new_labels = self.gen_labels(new_block_count, block.label)

                block_instructions = block.instructions
                block.remove_children()
                
                self.CFG.populate_block(block.label,
                        *(block_instructions[i] for i in range(0, self.max_size-1)))
                prev = block
                idx = self.max_size - 1
                i = 0
                while idx < num_instrs:
                    top = min(idx + self.max_size - 1, num_instrs)
                    if top + 1 == num_instrs:
                        # the +1 is for the next branch instruction
                        # so this uses the actual intended branch instruction
                        top = num_instrs

                    self.CFG.add_block(new_labels[i],
                            *(block_instructions[i] for i in range(idx, top)))
                    
                    new = self.CFG[new_labels[i]]
                    prev.add_child(new)

                    i += 1
                    idx = top
                    prev = new
            
            if changed:
                # this action is quite destructive, so it's unlikely any
                # analysis survives it
                preserved = ()

        # opt method MUST return list or tuple of all preserved analyses
        # it is strongly recommended that this list is made CONSERVATIVELY
        # for instance, I know that swapping does not affect the example
        # analysis, but I am not sure about other ones since I don't know
        # what other analyses may exist.
        return preserved

