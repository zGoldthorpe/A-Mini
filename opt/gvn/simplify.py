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
from opt.gvn.gargi import GVN

from ampy.passmanager import BadArgumentException
import ampy.types

class NaiveSimplify(Opt):
    # forward declaration
    pass

acc = {"rpo": (RPO, ()),
        "rpo-expr": (RPO, ("expr",)),
        "rpo-var": (RPO, ("var",)),
        "scc": (SCC, ()),
        "scc-expr": (SCC, ("expr",)),
        "scc-var": (SCC, ("var",)),
        "gargi": (GVN, ()),
        "any": ((RPO, SCC, GVN), ())}
acc_str = ", ".join(f'"{key}"' for key in acc)

class NaiveSimplify(NaiveSimplify):
    __doc__ = f"""
    Uses gvn-rpo or gvn-scc information to eliminate redundant definitions.
    Does not hoist or do anything advanced.

    gvn: {acc_str}
        Identify which GVN algorithm to use
    """

    @NaiveSimplify.init("gvn-reduce", gvn="any")
    def __init__(self, *, gvn):
        if gvn not in acc:
            raise BadArgumentException(f"`gvn` must be one of {acc_str}")
        self._gvn, self._args = acc[gvn]

    @NaiveSimplify.opt_pass
    def simplify(self):
        """
        Basic simplification algorithm
        """
        # Step 0. Compute value numbers
        # -----------------------------
        # The GVN algorithm will return a mapping from registers to
        # expressions, but this is too much for this simple reduction algo.
        # Therefore, we map these value numbers to a representative register
        # or an integer constant (if the expression is a constant)
        gvn = self.require(self._gvn, *self._args)
        self._vn = {}
        expr_rep = {} # lookup table for expression representative
        for var, expr in gvn.get_value_partitions().items():
            if isinstance(expr.op, int):
                self._vn[var] = str(expr.op)
            else:
                self._vn[var] = expr_rep.setdefault(expr, var)

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
                                    src.insert(-1, ampy.types.MovInstruction(val, ret))
                                    revived.add(val)
                                conds.append((val, label))
                            else:
                                # otherwise, we need to create a new copy
                                new = self._gen_new_phi_reg(ret)
                                self.CFG[label].insert(-1,
                                        ampy.types.MovInstruction(new, ret))
                                conds.append((new, label))
                        else:
                            conds.append((ret, label))
                    I.conds = tuple(conds)
                if isinstance(I, ampy.types.DefInstructionClass):
                    assigns.add(I.target)


        if self._changed:
            return tuple(opt for opt in self.opts if opt.ID in ("gvn-reduce", "ssa", "domtree"))
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
        if not vn.startswith('%'):
            return vn
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
                if not vn.startswith('%'):
                    # constant; remove definition
                    to_delete.append(i)
                    continue
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
