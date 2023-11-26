"""
Static single assignment
==========================
Goldthorpe

This pass converts code into SSA form (that is, every variable is only
defined once).

The algorithm used is that of

R. Cytron, J. Ferrante, B.K. Rosen, M.N. Wegman, F.K. Zadeck. 1991.
    "Efficiently computing static single assignment form and
        the control dependence graph"
    ACM Transactions on Programming Languages and Systems
    Vol. 13, No. 4.
    Pages 451--490.
"""

from utils.syntax import Syntax

from opt.tools import Opt, OptError
from opt.analysis.domtree import DomTreeAnalysis
from opt.analysis.defs import DefAnalysis
from opt.analysis.live import LiveAnalysis

import ampy.types

class SSA(Opt):
    # forward declaration
    pass

class SSA(SSA):
    """
    Runs the Cytron-Ferrante algorithm for converting code
    into static single assignment form.
    """

    @SSA.init("ssa")
    def __init__(self, /):
        pass

    @SSA.opt_pass
    def cytron_ferrante(self):
        """
        Cytron-Ferrante SSA form pass
        """

        # Step 1. Dominance frontier
        # --------------------------
        # The dominance frontier of a basic block B consists of all blocks B'
        # for which B dominates a parent of B', but B does not strictly
        # dominate B' itself.
        # Cytron-Ferrante computes the dominance frontier recursively.
        # Given the dominance frontier of all children of B in the dominator
        # tree, the dominance frontier of B is given as the union of:
        # 1. The local dominance frontier of B, consisting of all children of
        #    B in the CFG that are not strictly dominated by B, and
        # 2. The passed-up dominance frontier of each child B' of B, which
        #    consists of all blocks of the dominance frontier of B' that are
        #    not strictly dominated by the immediate dominator of B'
        #
        # df[B]: dominance frontier of B
        # ldf[B]: local dominance frontier of B
        # pdf[B]: passed-up dominance frontier of B
        self._df = {
                block : None
                for block in self.CFG
                }
        self._ldf = {
                block : None
                for block in self.CFG
                }
        self._pdf = {
                block : None
                for block in self.CFG
                }

        # Step 2. Iterated dominance frontier
        # -----------------------------------
        # The iterated dominance frontier of a set S is the result of taking
        # the limit of S_n, where S_0 := S, S_{n+1} := DF[S_0 + S_n].
        # We want the iterated dominance frontier for the set def[x] of
        # definitions of each variable x in the CFG
        # idf[var]: iterated dominance frontier of a variable
        self._idf = dict()
        defs = self.require(DefAnalysis)
        self._vars = set(defs.vars)

        for var in self._vars:
            blocks = defs.defs(var)
            if len(blocks) == 1:
                # phi nodes are unnecessary if there is only a single assignment to begin with
                continue
            S = set(blocks)
            self._idf[var] = S
            while True:
                new = self.dominance_frontier(*(S | self._idf[var]))
                if self._idf[var] == new:
                    break
                self._idf[var] = new

        # Step 3. Insert phi nodes
        # ------------------------
        # Phi nodes are inserted in the iterated dominance frontier
        # This handles "where", but to figure out "how", we traverse
        # the dominator tree to figure out the dominating use of each
        # variable prior to entering a "join" node.
        #
        # live_in[block]: set of all variables that are live coming in
        
        live = self.require(LiveAnalysis)
        self._live_in = {
                block : set(live.live_in(block))
                for block in self.CFG
                }
        self._reg = {var : 0 for var in self._idf} # for renaming
        self._dommem = {} # memoisation

        self._changed = False
        self._dfs_and_sub(self.CFG.entrypoint)

        # Step 4. Adjust phi node arguments
        # ---------------------------------
        # Now that the phi nodes are inserted, and dominating
        # names are calculated, we can use them to correct the phi nodes.
        #
        # NB. We need to be careful of when phi nodes are asking for arguments
        # which are redefined by a phi node inserted earlier in the same block.
        for block in self.CFG:
            assigns = set()
            for I in block:
                if isinstance(I, ampy.types.PhiInstruction):
                    conds = []
                    for var, label in I.conds:
                        parent = self.CFG[label]
                        reg = self._get_dominating_var(var, parent)
                        if reg in assigns:
                            # conflict!
                            tmp = self._new_reg(var)
                            parent._instructions.insert(
                                    ampy.types.MovInstruction(tmp, reg))
                            reg = tmp
                        conds.append((reg, label))
                    I.conds = tuple(conds)
                if isinstance(I, ampy.types.DefInstructionClass):
                    assigns.add(I.target)

        if self._changed:
            # I don't have any analyses on the CFG shape, which is the only thing that gets preserved
            return tuple(opt for opt in self.opts if opt.ID in ("ssa", "domtree"))
        return self.opts

    @(Syntax(object, ampy.types.BasicBlock) >> None)
    def _dfs_and_sub(self, block):
        """
        DFS traversal of dominator tree
        """
        # first, check if we need to define phi nodes
        for var, idf in self._idf.items():
            if block in idf and var in self._live_in[block]:
                conds = []
                for parent in block.parents:
                    # we will deal with which variable to use in a second pass
                    conds.append((var, parent.label))
                block._instructions.insert(0, ampy.types.PhiInstruction(var, *conds))
        # now, adjust variable definitions
        def sub(var):
            return self._get_dominating_var(var, block)

        for i, I in enumerate(block):
            # substitute operands with dominating names
            match type(I):
                case T if issubclass(T, ampy.types.BinaryInstructionClass):
                    I.operands = tuple(map(sub, I.operands))
                case ampy.types.MovInstruction | ampy.types.WriteInstruction:
                    I.operand = sub(I.operand)
                case ampy.types.BranchInstruction:
                    I.cond = sub(I.cond)
                case _:
                    # read, goto, exit, brkpt
                    # we deal with phi nodes later
                    pass

            # now create new definition, if necessary
            if isinstance(I, ampy.types.DefInstructionClass):
                var = self._new_reg(I.target)
                self._dommem.setdefault(block, {})[I.target] = var
                I.target = var

        for child in self.require(DomTreeAnalysis).children(block):
            self._dfs_and_sub(child)

    @(Syntax(object, str) >> str)
    def _new_reg(self, var):
        if var not in self._reg:
            # this means the variable is only defined once
            return var
        self._changed = True
        while (label := f"{var}.{self._reg[var]}") in self._vars:
            self._reg[var] += 1
        self._vars.add(label)
        return label

    @(Syntax(object, str, ampy.types.BasicBlock) >> str)
    def _get_dominating_var(self, var, block):
        """
        Returns the dominating name for a variable.
        """
        if not var.startswith('%'):
            return var
        if var not in self._dommem.setdefault(block, {}):
            if block == self.CFG.entrypoint:
                # all uses must be dominated by a definition
                # (this is also ensured by phi-node insertions)
                # this should be impossible, since liveness analysis is
                # run prior to SSA
                raise OptError(block, 0, f"{var} does not have a dominating name at {block.label}")
            idom = self.require(DomTreeAnalysis).idom(block)
            self._dommem[block][var] = self._get_dominating_var(var, idom)
        return self._dommem[block][var]

    @(Syntax(object, ampy.types.BasicBlock, ...) >> [set, ampy.types.BasicBlock])
    def dominance_frontier(self, *blocks):
        """
        Returns the dominance frontier of the given set of blocks
        """
        if len(blocks) == 0:
            return set()
        if len(blocks) > 1:
            return self.dominance_frontier(blocks[0]
                    ).union(self.dominance_frontier(*blocks[1:]))

        block = blocks[0]
        if self._df[block] is None:
            domtree = self.require(DomTreeAnalysis)

            # DF[B] = LDF[B] + Union(PDF[B'], B' domtree children of B)
            if self._ldf[block] is None:
                self._ldf[block] = set()
                # LDF[B]: CFG children B' of B not strictly dominated by B
                # i.e., either B' == B or B does not dominate B'
                for child in block.children:
                    if child == block or not domtree.dominates(block, child):
                        self._ldf[block].add(child)
            
            self._df[block] = set(self._ldf[block])
            for dtchild in domtree.children(block):
                if self._pdf[dtchild] is None:
                    # PDF[B] = {B' in DF[B] | B' not strictly dominated by idom[B]}
                    self._pdf[dtchild] = set()
                    idom = domtree.idom(dtchild)
                    for dfblock in self.dominance_frontier(dtchild):
                        if idom is None or idom == dfblock or not domtree.dominates(idom, dfblock):
                            self._pdf[dtchild].add(dfblock)

                self._df[block] |= self._pdf[dtchild]

        return self._df[block]

