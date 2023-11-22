"""
GVN-based simplify
====================
Goldthorpe

A simple implementation that tries to use GVN information
to simplify code
"""

from collections import deque

from utils.syntax import Syntax

from opt.tools import Opt
from opt.analysis.defs import DefAnalysis
from opt.analysis.domtree import DomTreeAnalysis
from opt.gvn.simpson import RPO, SCC

from ampy.passmanager import BadArgumentException
import ampy.types

class NaiveSimplify(Opt):
    # forward declaration
    pass

class NaiveSimplify(NaiveSimplify):
    """
    Uses gvn-rpo or gvn-scc information to eliminate redundant definitions.
    Does not hoist or do anything advanced.

    number: "var" or "expr" or "any"
        Set if the value numbers are given by consts/registers or expressions.
    gvn: "rpo" or "scc" or "any"
        Identify which GVN algorithm to use
    """

    @NaiveSimplify.init("gvn-reduce", "any", gvn="any")
    def __init__(self, number, *, gvn):
        if number not in ("var", "expr", "any"):
            raise BadArgumentException("`number` must be one of \"var\", \"expr\", or \"any\".")
        self._number = any if number == "any" else number
        if gvn not in ("rpo", "scc", "any"):
            raise BadArgumentException("`gvn` must be one of \"rpo\", \"scc\", or \"any\".")
        self._gvn = RPO if gvn == "rpo" else SCC if gvn == "scc" else (RPO, SCC)

    @NaiveSimplify.opt_pass
    def simplify(self):
        """
        Basic simplification algorithm
        """
        # Step 0. Compute value numbers
        # -----------------------------
        gvn = self.require(self._gvn, self._number)
        self._vn = gvn.get_value_partitions()
        defs = self.require(DefAnalysis)
        # remember locations of old defines, in case variables need to be revived
        defs.perform_opt()

        # Step 1. Perform substitutions
        # -----------------------------
        # To ensure substitutions and removed definitions are valid,
        # we perform a depth-first traversal of the dominator tree.
        # We don't touch phi nodes yet.
        # Note: it very well may be that some registers with the same
        # value number remain distinct in the final product.

        self._changed = False
        self._dommem = {} # memoisation
        self._dfs_and_sub(self.CFG.entrypoint)

        # Step 2. Correct phi nodes
        # -------------------------
        # We ignore phi nodes in the previous step so that we know
        # the dominating variable for each value at each block.
        # After value numbering, the phi node may depend
        # on a value class represented by a value that gets
        # redefined earlier in its own block, which is incorrect.
        # To correct this, we store the previous value before it gets
        # redefined. The choice of storing variable is a previously-discarded
        # copy, unless that is precisely the variable being copied
        revived = set()
        for block in self.CFG:
            assigns = set()
            for i, I in enumerate(block):
                if isinstance(I, ampy.types.PhiInstruction):
                    conds = []
                    for val, label in I.conds:
                        ret = self._get_dominating_var(val, self.CFG[label])
                        if ret in assigns:
                            # this means there is a conflict
                            if ret != val:
                                if val not in revived:
                                    src = defs.defs(val)[0]
                                    src._instructions.insert(-1, ampy.types.MovInstruction(val, ret))
                                    revived.add(val)
                                conds.append((val, label))
                            else:
                                # otherwise, we need to create a new copy
                                new = self._gen_new_phi_reg(ret)
                                self.CFG[label]._instructions.insert(-1,
                                        ampy.types.MovInstruction(new, ret))
                                conds.append((new, label))
                        else:
                            conds.append((ret, label))
                    I.conds = tuple(conds)
                if isinstance(I, ampy.types.DefInstructionClass):
                    assigns.add(I.target)


        if self._changed:
            return tuple(opt for opt in self.opts if opt.ID in ("gvn-simplify-naive", "ssa", "domtree"))
        return self.opts

    @(Syntax(object, str) >> str)
    def _gen_new_phi_reg(self, var):
        """
        Generate a new register name (used for holding phi argument values)
        """
        ret = f"{var}.phi"
        idx = -1
        while ret in self._vn:
            idx += 1
            ret = f"{var}.phi.{idx}"
        self._vn[ret] = self_vn[var] # so it doesn't get used again
        return ret

    @(Syntax(object, str, ampy.types.BasicBlock) >> (str, None))
    def _get_dominating_var(self, var, block):
        """
        Returns the dominating definition of a variable, or None
        if this value number class has not been defined yet along this
        path in the dominator tree.
        """
        if not var.startswith('%'):
            return var
        vn = self._vn[var]
        if isinstance(vn, int):
            return str(vn)
        if vn not in self._dommem.setdefault(block, {}):
            if block == self.CFG.entrypoint:
                # this means the variable has never been defined
                # in this path along the dominator tree
                self._dommem[block][vn] = None
            else:
                # walk up dominating tree until you find its definition
                idom = self.require(DomTreeAnalysis).idom(block)
                self._dommem[block][vn] = self._get_dominating_var(var, idom)

        return self._dommem[block][vn]

    @(Syntax(object, ampy.types.BasicBlock) >> None)
    def _dfs_and_sub(self, block):
        """
        Depth-first traversal of dominator tree
        """

        def sub(var):
            ret = self._get_dominating_var(var, block)
            self._changed |= ret != var
            return ret
        
        to_delete = []
        for i, I in enumerate(block):
            # substitute operands first
            if isinstance(I, ampy.types.BinaryInstructionClass):
                I.operands = tuple(map(sub, I.operands))
            elif isinstance(I, ampy.types.MovInstruction):
                I.operand = sub(I.operand)
            elif isinstance(I, ampy.types.BranchInstruction):
                I.cond = sub(I.cond)
            elif isinstance(I, ampy.types.WriteInstruction):
                I.operand = sub(I.operand)
            else: # read, phi, goto, exit, brkpt
                # Note: we will handle phi nodes afterwards
                pass
            
            # handle definitions
            if isinstance(I, ampy.types.DefInstructionClass):
                vn = self._vn[I.target]
                rep = self._get_dominating_var(I.target, block)
                if rep is None:
                    # value has not been computed yet
                    self._dommem[block][vn] = I.target
                    continue
                # otherwise, value has already been computed
                # so this definition is redundant
                self._changed = True
                to_delete.append(i)
    
        for i in reversed(to_delete):
            block._instructions.pop(i)

        for child in self.require(DomTreeAnalysis).children(block):
            self._dfs_and_sub(child)
