"""
Register reallocation
=======================
Goldthorpe

Simple pass that tries to minimise the number of registers used.

Based on register allocation, though spilling is impossible in this
virtual environment.

R. Briggs, K.D. Cooper, K. Kennedy, L. Torezon. 1989.
    "Colouring heuristics for register allocation"
    ACM SIGPLAN Notices
    Vol. 24, No. 7.
    Pages 275--284.
"""

from ampy.ensuretypes import Syntax
from ampy.passmanager import BadArgumentException
from opt.tools import Opt

from opt.analysis.live import LiveAnalysis

import ampy.types

class RR(Opt):
    # forward declaration
    pass

class RR(RR):
    """
    reg-realloc(num, /)

    Reduce number of registers used. (Obfuscates register names)

    num: int
        Number of registers to try and allocate to.
        Pass will target the maximum between this input number and the
        lower bound it determines via live analysis.
        This is used to determine \"spillage\".
        (default: 0)
    """

    @RR.init("reg-realloc", "0")
    def __init__(self, num_reg, /):
        try:
            self.num_reg = int(num_reg)
        except ValueError:
            raise BadArgumentException("Position argument of RR must be an integer.")

    @RR.opt_pass
    def reg_realloc(self):
        """
        Briggs et al
        """

        # Step 1. Build register interference graph
        # -----------------------------------------
        # The RIG has registers as nodes, and edges wherever two registers
        # are simultaneously live.
        # Copy instructions are labelled for possible coalescing.
        #
        # rig[var]: adjacent nodes in RIG to var
        # cp[var]: set of copy instructions

        live = self.require(LiveAnalysis)
        self.RIG = {}
        self.cp = {}
        for block in self.CFG:
            for i, I in enumerate(block):
                regs = live.live_in(block, i)
                self.num_reg = max(self.num_reg, len(regs))
                for u in regs:
                    self.RIG.setdefault(u, set())
                for u in regs:
                    for v in regs:
                        if u >= v:
                            continue
                        self.debug("int:", u, "<->", v)
                        self.RIG[u].add(v)
                        self.RIG[v].add(u)
                # also add conflicts between conditionally live instructions
                for parent, cond_regs in live.live_in_phi(block, i).items():
                    self.num_reg = max(self.num_reg, len(regs) + len(cond_regs))
                    for u in cond_regs:
                        self.RIG.setdefault(u, set())
                    for u in regs + cond_regs:
                        for v in cond_regs:
                            if u == v:
                                continue
                            self.debug("phi:", u, "<->", v)
                            self.RIG[u].add(v)
                            self.RIG[v].add(u)

                if isinstance(I, ampy.types.MovInstruction):
                    if I.operand.startswith('%') and I.operand != I.target:
                        self.debug("mov:", I.target, "===", I.operand)
                        self.cp.setdefault(I.target, set()).add(I.operand)
                        self.cp.setdefault(I.operand, set()).add(I.target)
                elif isinstance(I, ampy.types.PhiInstruction):
                    for reg, _ in I.conds:
                        if not reg.startswith('%') or reg == I.target:
                            continue
                        self.debug("phi:", I.target, "===", reg)
                        self.cp.setdefault(I.target, set()).add(reg)
                        self.cp.setdefault(reg, set()).add(I.target)

        self.debug("RIG completed")
        self.debug("Target register count:", self.num_reg)

        # Step 2. Simplify RIG
        # --------------------
        # Register allocation amounts to a colouring of the RIG
        # This is NP-hard to do minimally, so we use the procedure
        # simplify -> coalesce -> freeze -> spill
        #       ^______|___________|_________|
        # - simplify: remove a node with < K neighbours in RIG
        #             (NB: you cannot simplify if node is part of a copy)
        # - coalesce: merge nodes bridged by a copy if < K total neighbours
        # - freeze:  remove copy bridge
        #
        # stack: consists of (var, {neighbours}), pushed while simplifying
        stack = [] # for determining the order of graph colouring

        while len(self.RIG) > 0:
            var, neighbours = min(self.RIG.items(),
                    key=lambda item: (
                        len(item[1]) >= self.num_reg, # 0 => no-spill
                        item[0] in self.cp,           # 0 => no copy
                        len(item[1])))
            # sort vars by number of registers, but with modified priority:
            # non-spill < copy < may-spill
            # (note: False < True)
            if var in self.cp:
                # test for coalesce
                candidates = ((cp, self.RIG[cp] | neighbours) for cp in self.cp[var])
                cp, combined = min(candidates, key=lambda item: (
                            len(item[1]) >= self.num_reg,
                            len(item[1])))
                # coalescing is not possible if the registers also interfere
                if len(combined) >= self.num_reg or cp in neighbours:
                    self.freeze(var, cp)
                    continue
                # otherwise, we may coalesce
                self.coalesce(var, cp)
                continue

            # not a copy, so we are committing to colouring this node
            self.debug("Pushing", var, neighbours)
            stack.append((var, neighbours))
            self.simplify_rig(var)

        # Step 3. Register allocation
        # ---------------------------
        # Pop the stack and optimistically colour the processed RIG
        #
        # col[var]: integer "colour" assigned to each register
        # count: largest unused integer colour
        count = 0
        spills = 0
        self._col = {}
        for var, neighbours in reversed(stack):
            num = min(set(range(count+1)) - {self._col[n] if isinstance(n, str) else self._col[n[0]] for n in neighbours})
            if not isinstance(var, tuple):
                var = (var,)
            for v in var:
                self.debug("Allocating", v, "=>", num)
                if num >= self.num_reg:
                    spills += 1
                self._col[v] = num
            self._col[var] = num
            if num == count:
                count += 1

        self.debug("Spills:", spills)

        # Step 4. Assign registers
        # ------------------------
        # Use the colouring determined above to transform the code.
        def sub(var):
            if var.startswith('%'):
                return f"%{self._col[var]}"
            return var

        for block in self.CFG:
            to_delete = []
            for i, I in enumerate(block):
                if isinstance(I, ampy.types.DefInstructionClass):
                    if I.target in self._col:
                        I.target = sub(I.target)
                    elif isinstance(I, ampy.types.ReadInstruction):
                        I.target = "%_"
                    else: # dead variable, and not a read
                        to_delete.append(i)
                        continue

                if isinstance(I, ampy.types.BinaryInstructionClass):
                    I.operands = tuple(map(sub, I.operands))
                elif isinstance(I, ampy.types.MovInstruction):
                    I.operand = sub(I.operand)
                    if I.target == I.operand:
                        to_delete.append(i)
                elif isinstance(I, ampy.types.PhiInstruction):
                    I.conds = tuple(map(lambda p: (sub(p[0]), p[1]), I.conds))
                    if len(set(var for var, _ in I.conds)) == 1:
                        if I.target == I.conds[0][0]:
                            to_delete.append(i)
                        else:
                            block._instructions[i] = ampy.types.MovInstruction(I.target, I.conds[0][0])
                elif isinstance(I, ampy.types.BranchInstruction):
                    I.cond = sub(I.cond)
                elif isinstance(I, ampy.types.WriteInstruction):
                    I.operand = sub(I.operand)
                else:
                    # read, goto, exit, brkpt
                    pass

            for i in reversed(to_delete):
                block._instructions.pop(i)

        return tuple(opt for opt in self.opts if opt.ID in ("reg-realloc", "domtree"))

    @(Syntax(object, (str, (tuple, [tuple, str]))) >> None)
    def simplify_rig(self, var):
        """
        Remove var from RIG
        """
        neighbours = self.RIG.pop(var)
        for reg in neighbours:
            self.RIG[reg].remove(var)
        # no need to handle copies, because the RIG cannot simplify
        # copy instructions

    @(Syntax(object, (str, (tuple, [tuple, str])), (str, (tuple, [tuple, str]))) >> None)
    def coalesce(self, var, cp):
        """
        Coalesce variable var with its copy cp in RIG
        """
        self.debug("Coalescing", var, "===", cp)
        vnb = self.RIG.pop(var)
        cnb = self.RIG.pop(cp)
        vcp = self.cp.pop(var) - {cp}
        ccp = self.cp.pop(cp) - {var}
        join = tuple(sorted(
            (var if isinstance(var, tuple) else (var,)) +
            (cp if isinstance(cp, tuple) else (cp,))))

        self.RIG[join] = vnb | cnb
        for reg in self.RIG[join]:
            self.RIG[reg] -= {var, cp}
            self.RIG[reg].add(join)

        self.cp[join] = vcp | ccp
        for reg in self.cp[join]:
            self.cp[reg] -= {var, cp}
            self.cp[reg].add(join)

        if len(self.cp[join]) == 0:
            del self.cp[join]

    @(Syntax(object, (str, (tuple, [tuple, str])), (str, (tuple, [tuple, str]))) >> None)
    def freeze(self, var, cp):
        """
        Freeze copy instruction from ever coalescing
        """
        self.debug("Freezing", var, "===", cp)
        self.cp[var].remove(cp)
        self.cp[cp].remove(var)
        if len(self.cp[var]) == 0:
            del self.cp[var]
        if len(self.cp[cp]) == 0:
            del self.cp[cp]
