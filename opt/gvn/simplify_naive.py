"""
GVN-based simplify
====================
Goldthorpe

A simple implementation that tries to use information from gvn-simple
to simplify code
"""

from collections import deque

from utils.syntax import Syntax

from opt.tools import Opt
from opt.analysis.domtree import DomTreeAnalysis
from opt.gvn.rpo_simple import RPO

import ampy.types

class NaiveSimplify(Opt):
    # forward declaration
    pass

class NaiveSimplify(NaiveSimplify):
    """
    Uses gvn-simple information to eliminate redundant definitions.
    Does not hoist or do anything advanced.

    Pass gvn-simple with desired arguments prior to this pass to affect
    the value numbering.
    """

    @NaiveSimplify.init("gvn-simplify-naive")
    def __init__(self, /):
        pass

    @NaiveSimplify.opt_pass
    def simplify(self):
        """
        Basic simplification algorithm
        """
        # Step 0. Compute value numbers
        # -----------------------------
        # vn[var]: value number of variable
        # const[i]: if applicable, the constant value of vn class
        gvn = self.require(RPO)
        self._vn = {}
        self._const = {}
        number = 0
        for var in gvn["classes"]:
            if var == '$':
                number += 1
                continue
            if not var.startswith('%'):
                # this is a constant
                self._const[number] = var
                continue
            self.debug(f"Assigning {var} to value number {number}")
            self._vn[var] = number

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
        # the dominating variable for each value at each block
        for block in self.CFG:
            for i, I in enumerate(block):
                if not isinstance(I, ampy.types.PhiInstruction):
                    continue
                I.conds = tuple(
                    (self._get_dominating_var(val, self.CFG[label]), label)
                    for val, label in I.conds)

        if self._changed:
            return tuple(opt for opt in self.opts if opt.ID in ("gvn-simplify-naive", "ssa", "domtree"))
        return self.opts

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
        if vn in self._const:
            return self._const[vn]
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
