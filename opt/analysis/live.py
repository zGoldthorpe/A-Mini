"""
Liveness
==========
Goldthorpe

This module performs liveness opt on a CFG.
"""

from ampy.ensuretypes import Syntax
from opt.tools import Opt, OptError

import ampy.types
import ampy.debug

class LiveAnalysis(Opt):
    # forward declaration
    pass

class LiveAnalysis(LiveAnalysis):
    """
    live

    Determines the live-in and live-out sets for every block and instruction.
    Note: liveness of a variable in a phi node is fuzzy. If a block @A has
    a phi node
    @A:
        %0 = phi [ %1, @B ], ...
        ...
    then the variable %1 will be declared live coming out of @B, but will *not*
    be declared live coming into @A, because liveness is conditional on arriving
    through @B.
    """

    @LiveAnalysis.init("live")
    def __init__(self, /):
        pass

    @LiveAnalysis.opt_pass
    def flow_opt(self):
        """
        Liveness is a backward-propagation flow opt, using the rules

        live_out[I] = union(live_in[I'] for successors I' of I)
        live_in[I] = (live_out[I] - defs[I]) + use[I]

        However, things are a bit hairy with phi nodes. We work around this
        by declaring the operands of phi nodes to *not* count as uses, but
        then append them to the live_out sets of their specified source labels

        Initialisation takes live_in[I] = empty for all I
        """
        self._in = {block:set() for block in self.CFG}
        self._out = {}

        # process phi nodes first
        self._phi = {block:set() for block in self.CFG}
        for block in self.CFG:
            for I in block:
                if isinstance(I, ampy.types.PhiInstruction):
                    for val, label in I.conds:
                        if val.startswith('%'):
                            self._phi[self.CFG[label]].add(val)

        changed = True
        while changed:
            ampy.debug.print(self.ID, "running flow opt")
            self._visited = set()
            changed = self._back_propagate(self.CFG.entrypoint)

        # check for undefined variables:
        if len(self._in[self.CFG.entrypoint]) > 0:
            raise OptError(self.CFG.entrypoint, 0, f"The following variables were uninitialised: {', '.join(self._in[self.CFG.entrypoint])}")

        # now, write results to metadata
        for block in self.CFG:
            if block not in self._out:
                # only possible if block is unreachable
                continue
            self.assign(block, "in", *sorted(self._in[block]))
            self.assign(block, "out", *sorted(self._out[block]))
            for i in range(len(block)):
                self.assign(block, i, "in", *sorted(self._in[block, i]))
                self.assign(block, i, "out", *sorted(self._out[block, i]))

        return self.opts

    @(Syntax(object, ampy.types.BasicBlock) >> bool)
    def _back_propagate(self, block):
        """
        Perform back propagation until a fixedpoint is reached
        Returns True if the propagation causes an update
        """
        changed = False
        self._visited.add(block)

        for child in block.children:
            # back propagation, so recurse first, and then propagate
            if child in self._visited:
                continue
            changed |= self._back_propagate(child)

        # now, process instructions in reverse
        # branch instruction gets special treatment
        br = len(block) - 1

        old_out = self._out.get((block,br), set())
        old_in = self._in.get((block,br), set())

        self._out[block,br] = self._phi[block]
        # live-out always includes specific variables from phi nodes
        for child in block.children:
            self._out[block,br] |= self._in[child]

        defs, uses = self._def_use(block[br])
        self._in[block,br] = (self._out[block,br] - defs) | uses

        changed |= (old_out != self._out[block,br])
        changed |= (old_in != self._in[block,br])

        for i in range(br-1, -1, -1):
            old_out = self._out.get((block,i), set())
            old_in = self._in.get((block,i), set())

            self._out[block,i] = self._in[block,i+1]
            defs, uses = self._def_use(block[i])
            self._in[block,i] = (self._out[block,i] - defs) | uses

            changed |= (old_out != self._out[block,i])
            changed |= (old_in != self._in[block,i])

        # finally, define live-in and live-out for the block
        # (though, no need to track changes)
        self._in[block] = self._in[block, 0]
        self._out[block] = self._out[block, len(block)-1]

        return changed

    @(Syntax(object, ampy.types.InstructionClass) >> ((), [set, str], [set, str]))
    def _def_use(self, I):
        """
        Returns the pair ({definitions}, {uses}) for an instruction

        N.B. uses may be constants
        """
        def reg_set(*ins):
            return set(filter(lambda s: s.startswith('%'), ins))

        if isinstance(I, (ampy.types.BinaryInstructionClass)):
            return {I.target}, reg_set(*I.operands)
        if isinstance(I, ampy.types.MovInstruction):
            return {I.target}, reg_set(I.operand)
        if isinstance(I, ampy.types.PhiInstruction):
            # operands of a phi node do *not* count as uses
            # they are instead handled separately
            return {I.target}, set()
        if isinstance(I, ampy.types.BranchInstruction):
            return set(), reg_set(I.cond)
        if isinstance(I, ampy.types.ReadInstruction):
            return {I.target}, set()
        if isinstance(I, ampy.types.WriteInstruction):
            return set(), reg_set(I.operand)
        # remaining: GotoInstruction, ExitInstruction, BrkInstruction
        return set(), set()
