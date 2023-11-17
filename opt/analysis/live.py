"""
Liveness
==========
Goldthorpe

This module performs liveness opt on a CFG.
"""

from utils.syntax import Syntax
from opt.tools import Opt, OptError

from ampy.passmanager import BadArgumentException
import ampy.types

class LiveAnalysis(Opt):
    # forward declaration
    pass

class LiveAnalysis(LiveAnalysis):
    """
    Determines the live-in and live-out sets for every block and instruction.
    Note: liveness of a variable in a phi node is fuzzy.
    If a block @A has a phi node
    @A:
        %0 = phi [ %1, @B ], ...
        ...
    then the liveness of %1 is conditional on entering through @B.
    Therefore, live_in consists of unconditionally live variables, and
    live_phi gives live variables conditional on the previous block label.
    """

    @LiveAnalysis.init("live")
    def __init__(self):
        pass

    @LiveAnalysis.getter
    @(Syntax(object, ampy.types.BasicBlock)
      | Syntax(object, ampy.types.BasicBlock, int)
      >> [tuple, str])
    def live_in(self, block, idx=None, /):
        """
        Give unconditionally live variables coming into block or instruction
        """
        if idx is None:
            return tuple(self.get(block, "in", default=[]))
        return tuple(self.get(block, idx, "in", default=[]))

    @LiveAnalysis.getter
    @(Syntax(object, ampy.types.BasicBlock)
      | Syntax(object, ampy.types.BasicBlock, int)
      >> {ampy.types.BasicBlock : [tuple, str]})
    def live_in_phi(self, block, idx=None, /):
        if idx is None:
            return {parent : tuple(self.get(block, f"in/{parent.label}", default=[]))
                        for parent in block.parents}
        return {parent : tuple(self.get(block, idx, f"in/{parent.label}", default=[]))
                    for parent in block.parents}

    @LiveAnalysis.getter
    @(Syntax(object, ampy.types.BasicBlock)
      | Syntax(object, ampy.types.BasicBlock, int)
      >> [tuple, str])
    def live_out(self, block, idx=None, /):
        if idx is None:
            return tuple(self.get(block, "out", default=[]))
        return tuple(self.get(block, idx, "out", default=[]))

    @LiveAnalysis.opt_pass
    def flow_opt(self):
        """
        Liveness is a backward flow analysis, using the rules

        live_out[I] = union(live_in[I'] for successors I' of I)
        live_in[I] = (live_out[I] - defs[I]) + use[I]

        However, things are a bit hairy with phi nodes. We work around this
        by declaring the operands of phi nodes to *not* count as uses, but
        then append them to the live_out sets of their specified source labels

        Initialisation takes live_in[I] = empty for all I
        """
        self._in = {block:set() for block in self.CFG}
        self._out = {}

        # compute conditional live-in sets first
        # (these do not require back-propagation)
        self._in_phi = {}
        for block in self.CFG:
            phi_in = {parent.label:set() for parent in block.parents}
            for i, I in reversed(list(enumerate(block))):
                if isinstance(I, ampy.types.PhiInstruction):
                    for var, lbl in I.conds:
                        if var.startswith('%'):
                            phi_in[lbl].add(var)

                self._in_phi[block, i] = {parent : set(phi_in[parent.label])
                                            for parent in block.parents}

            self._in_phi[block] = {parent : phi_in[parent.label]
                                    for parent in block.parents}


        changed = True
        while changed:
            self.debug("running flow analysis")
            self._visited = set()
            changed = self._back_flow(self.CFG.entrypoint)

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
            for parent in block.parents:
                self.assign(block, f"in/{parent.label}", *sorted(self._in_phi[block][parent]))

            for i in range(len(block)):
                self.assign(block, i, "in", *sorted(self._in[block, i]))
                self.assign(block, i, "out", *sorted(self._out[block, i]))
                for parent in block.parents:
                    self.assign(block, i, f"in/{parent.label}", *sorted(self._in_phi[block, i][parent]))

        return self.opts

    @(Syntax(object, ampy.types.BasicBlock) >> bool)
    def _back_flow(self, block):
        """
        Perform backward flow analysis until a fixedpoint is reached
        Returns True if the propagation causes an update
        """
        changed = False
        self._visited.add(block)

        for child in block.children:
            # back propagation, so recurse first, and then propagate
            if child in self._visited:
                continue
            changed |= self._back_flow(child)

        # now, process instructions in reverse
        # branch instruction gets special treatment
        br = len(block) - 1

        old_out = self._out.get((block,br), set())
        old_in = self._in.get((block,br), set())
        
        self._out[block, br] = set()
        for child in block.children:
            self._out[block, br] |= self._in[child] | self._in_phi[child][block]

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

        if isinstance(I, ampy.types.BinaryInstructionClass):
            return {I.target}, reg_set(*I.operands)
        if isinstance(I, ampy.types.MovInstruction):
            return {I.target}, reg_set(I.operand)
        if isinstance(I, ampy.types.PhiInstruction):
            # conditional uses don't count in this case
            # they are handled separately
            return {I.target}, set()
        if isinstance(I, ampy.types.BranchInstruction):
            return set(), reg_set(I.cond)
        if isinstance(I, ampy.types.ReadInstruction):
            return {I.target}, set()
        if isinstance(I, ampy.types.WriteInstruction):
            return set(), reg_set(I.operand)
        # remaining: GotoInstruction, ExitInstruction, BrkInstruction
        return set(), set()
