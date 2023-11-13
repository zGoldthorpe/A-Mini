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

from opt.tools import Opt
from opt.analysis.domtree import DomTreeAnalysis
from opt.analysis.defs import DefAnalysis
from opt.analysis.live import LiveAnalysis

import ampy.types

class SSA(Opt):
    # forward declaration
    pass

class SSA(SSA):
    """
    ssa

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

        for var in defs.vars:
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

        self.debug("IDFs:", {var:{B.label for B in self._idf[var]} for var in self._idf})

        # Step 3. Insert phi nodes
        # ------------------------
        # Phi nodes are inserted in the iterated dominance frontier
        # This handles "where", but to figure out "how", we traverse
        # the CFG via DFS to track which definition of each variable
        # is "last used"
        #
        # live_in[block]: set of all variables that are live coming in
        
        live = self.require(LiveAnalysis)
        self._live_in = {
                block : set(live.live_in(block))
                for block in self.CFG
                }

        changed = False
        for var, blocks in self._idf.items():
            # SSA_vars: list of new variables for substituting var
            # SSA_counter: key for uniqueness of variable
            # visited: set of basic blocks that have been visited
            # phi[B]: phi node conditions for var at block B
            # phi_idx[B]: name of phi variable defined at B, if any
            self._ssa_vars = []
            self._ssa_counter = -1
            self._visited = set()
            self._phi = {block : [] for block in blocks}
            self._phi_idx = {}

            changed |= self._prepare_phi_nodes(var, -1, self.CFG.entrypoint)

            # now that the phi nodes are prepared, we can actually add them
            for block, conds in self._phi.items():
                if len(conds) == 0:
                    # there is no phi node
                    continue
                changed = True
                newvar = self._ssa_vars[self._phi_idx[block]]
                block._instructions.insert(0,
                        ampy.types.PhiInstruction(newvar, *conds))

        if changed:
            # I don't have any analyses on the CFG shape, which is the only thing that gets preserved
            return tuple(opt for opt in self.opts
                        if isinstance(opt, SSA))
        return self.opts

    @(Syntax(object, str) >> int)
    def _gen_register(self, var):
        """
        Generates register names for converting var into SSA
        and stores them in SSA_vars
        Returns index of new register
        """
        defs = self.require(DefAnalysis)

        while True:
            self._ssa_counter += 1
            reg = f"{var}.{self._ssa_counter}"
            if reg not in defs.vars:
                self._ssa_vars.append(reg)
                return len(self._ssa_vars)-1


    @(Syntax(object, str, int, ampy.types.BasicBlock, src=ampy.types.BasicBlock) >> bool)
    def _prepare_phi_nodes(self, var, cur_idx, block, *, src=None):
        """
        Performs a DFS to build phi nodes and update variable names
        However, does not insert phi nodes yet.

        Returns True if preparation changes the CFG
        """
        changed = False
        if block in self._idf[var]:
            if var in self._live_in[block]:
                # variable is actually used
                # so phi node is necessary
                if src.label not in (lbl for _, lbl in self._phi[block]):
                    self._phi[block].append((self._ssa_vars[cur_idx], src.label))
                if block not in self._phi_idx:
                    self._phi_idx[block] = self._gen_register(var)
                    self.debug(f"Inserting new phi variable {self._ssa_vars[self._phi_idx[block]]} in {block.label}")

        prev = (cur_idx := self._phi_idx.get(block, cur_idx))
        for I in block:
            cur_idx = self._replace_and_update(I, var, cur_idx, src=src)
            changed |= prev != (prev := cur_idx)

        if block not in self._visited:
            self._visited.add(block)
            for child in block.children:
                changed |= self._prepare_phi_nodes(var, cur_idx, child, src=block)
        return changed

    @(Syntax(object, ampy.types.InstructionClass, str, int, src=(ampy.types.BasicBlock, None)) >> int)
    def _replace_and_update(self, I, var, idx, src=None):
        """
        Replace all uses of var with _ssa_vars[idx].
        If var is redefined, replaces redefinition with _ssa_vars[_ssa_idx+1].

        Returns the current index of _ssa_vars
        """
        def sub(v):
            if v != var:
                return v
            if idx < 0 or idx >= len(self._ssa_vars):
                raise IndexError(f"Did not prepare enough substitutes for {var} (requesting index {idx})")
            return self._ssa_vars[idx]

        if isinstance(I, ampy.types.BinaryInstructionClass):
            I.operands = tuple(map(sub, I.operands))
        elif isinstance(I, ampy.types.MovInstruction):
            I.operand = sub(I.operand)
        elif isinstance(I, ampy.types.PhiInstruction):
            label = "" if src is None else src.label
            I.conds = tuple(map(
                lambda t: (sub(t[0]) if t[1] == label else t[0],
                    t[1]), I.conds))
        elif isinstance(I, ampy.types.BranchInstruction):
            I.cond = sub(I.cond)
        elif isinstance(I, ampy.types.WriteInstruction):
            I.operand = sub(I.operand)
        else: # read, goto, exit, brkpt
            pass

        if isinstance(I, ampy.types.DefInstructionClass) and I.target == var:
            # redefinition needs a new variable
            idx = self._gen_register(var)
            I.target = sub(I.target)
            self.debug(f"Inserting new variable {I.target}")

        return idx

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

