"""
Dead code elimination
=======================
Goldthorpe

Dead code elimination pass based on the observation that registers
are only important if they dictate a branch, or are written to output.
"""

from utils.syntax import Syntax

from opt.tools import Opt

import ampy.types

class DCE(Opt):
    # forward declaration
    pass

class DCE(DCE):
    """
    dce

    Eliminates definitions that do not eventually lead to a branch condition
    or a write to output.
    """

    @DCE.init("dce")
    def __init__(self, /):
        pass

    @DCE.opt_pass
    def eliminate(self):

        # Step 1. Perform observability analysis
        # --------------------------------------
        # Say a register is "observable" if it affects a branch condition or
        # program output. This can be determined with backward flow analysis.
        #
        # obs-out[I] = union(obs-in[I'] for successors I' of I)
        # obs-in[I] = (obs-out[I] - defs[I]) + obs-uses[I]
        #
        # initialised with obs-in[I] = empty for all I
        # obs-uses[I] consists of registers used to define an observable
        # register
        #
        # (the defs[I] term is unnecessary if code is in SSA form)

        self._out = {}
        self._in = {}
        
        updating = True
        while updating:
            self.debug("running flow analysis")
            updating = self._back_flow(self.CFG.entrypoint, set())

        # Step 2. Eliminate non-obsed definitions
        # -----------------------------------------
        # Remove all definitions of unobsed variables.
        # Only exception are read instructions, which must be left in
        # even if the input is never used.
        changed = False
        for block in self.CFG:
            to_delete = []
            for i, I in enumerate(block):
                if not isinstance(I, ampy.types.DefInstructionClass):
                    # non-definition instructions cannot be eliminated
                    continue
                if isinstance(I, ampy.types.ReadInstruction):
                    # reads cannot be eliminated
                    continue
                if I.target not in self._out[block, i]:
                    changed = True
                    to_delete.append(i)

            for i in reversed(to_delete):
                block._instructions.pop(i)

        if changed:
            return tuple(opt for opt in self.opts if opt.ID in ("dce", "ssa"))
        return self.opts

    @(Syntax(object, ampy.types.BasicBlock, set) >> bool)
    def _back_flow(self, block, seen):
        """
        Perform backward flow analysis
        Return True if the flow causes an update
        """
        updated = False
        seen.add(block)
        for child in block.children:
            if child not in seen:
                updated |= self._back_flow(child, seen)

        # now, process instructions in reverse
        br = len(block) - 1

        old_out = self._out.get((block, br), set())
        old_in = self._in.get((block, br), set())

        self._out[block, br] = set()
        for child in block.children:
            self._out[block, br] |= self._in.get((child, 0), set())

        defs, uses = self._def_use(block[br], self._out[block, br])
        self._in[block, br] = (self._out[block, br] - defs) | uses

        updated |= (old_out != self._out[block, br])
        updated |= (old_in != self._in[block, br])

        for i in range(br-1, -1, -1):
            old_out = self._out.get((block, i), set())
            old_in = self._in.get((block, i), set())

            self._out[block, i] = self._in[block, i+1]
            defs, uses = self._def_use(block[i], self._out[block, i])
            self._in[block, i] = (self._out[block, i] - defs) | uses

            updated |= (old_out != self._out[block, i])
            updated |= (old_in != self._in[block, i])

        return updated

    @(Syntax(object, ampy.types.InstructionClass, set) >> ((), [set, str], [set, str]))
    def _def_use(self, I, out):
        """
        Returns the pair ({definitions}, {obs-uses}) for an instruction
        """
        if isinstance(I, ampy.types.DefInstructionClass):
            if I.target not in out:
                # target is not observable
                # so the uses are not observable
                return set(), set()
        
        def reg_set(*ins):
            return set(filter(lambda s: s.startswith('%'), ins))

        if isinstance(I, ampy.types.BinaryInstructionClass):
            return {I.target}, reg_set(*I.operands)
        if isinstance(I, ampy.types.MovInstruction):
            return {I.target}, reg_set(I.operand)
        if isinstance(I, ampy.types.PhiInstruction):
            return {I.target}, reg_set(*(val for val, _ in I.conds))
        if isinstance(I, ampy.types.BranchInstruction):
            return set(), reg_set(I.cond)
        if isinstance(I, ampy.types.ReadInstruction):
            return {I.target}, set()
        if isinstance(I, ampy.types.WriteInstruction):
            return set(), reg_set(I.operand)
        # remaining: GotoInstruction, ExitInstruction, BrkInstruction
        return set(), set()
