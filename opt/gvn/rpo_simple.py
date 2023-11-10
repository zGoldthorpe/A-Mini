"""
Simple RPO GVN
================
Goldthorpe

This implements a simplified version of the RPO algorithm found
in figure 4.3 Simpson's PhD Thesis.

L.T. Simpson. 1996
    "Value-Driven Redundancy Elimination"
    PhD Thesis, Rice University
"""

from ampy.ensuretypes import Syntax
from ampy.passmanager import BadArgumentException
from opt.ssa import SSA
from opt.tools import Opt
from opt.gvn.simple_poly import Polynomial

import ampy.types
import ampy.debug

class RPO(Opt):
    # forward declaration
    pass

class RPO(RPO):
    """
    gvn-simple(mode)

    Runs a simple version of Simpson's RPO GVN algorithm

    mode: "simple" or "poly"
        In simple mode, value numbers are given by registers or constants.
        In poly mode, value numbers are given by polynomial expressions.
    """

    @RPO.init("gvn-simple", "simple")
    def __init__(self, mode, /):
        if mode not in ["simple", "poly"]:
            raise BadArgumentException("Mode must be one of \"simple\" or \"poly\".")
        self._mode = mode

    @RPO.opt_pass
    def rpo_pass(self):
        """
        RPO algorithm
        """
        # Step 0. Assert SSA form
        # -----------------------
        self.require(SSA).perform_opt()

        # Step 1. Get blocks in reverse post-order
        # ----------------------------------------
        postorder = []
        
        seen = set()
        def build_postorder(block):
            seen.add(block)
            for child in block.children:
                if child not in seen:
                    build_postorder(child)
            postorder.append(block)
        
        build_postorder(self.CFG.entrypoint)

        # Step 2. Value numbering
        # -----------------------
        # Repeat value lookup until a fixedpoint is found
        vn = {}
        def vnpoly(op):
            if op.startswith('%'):
                return vn.get(op, Polynomial('%?'))
            return Polynomial(op)

        while True:
            ampy.debug.print(self.ID, "Updating value numbers")
            lookup = {}
            changed = False
            for block in reversed(postorder):
                for I in block:

                    if isinstance(I, ampy.types.MovInstruction):
                        expr = vnpoly(I.operand)

                    elif isinstance(I, ampy.types.PhiInstruction):
                        if len(set(vnpoly(val) for val, _ in I.conds)) == 1:
                            expr = vnpoly(I.conds[0][0])
                        else:
                            expr = Polynomial(I.target)

                    elif isinstance(I, ampy.types.ArithInstructionClass):
                        op1, op2 = map(vnpoly, I.operands)
                        if isinstance(I, ampy.types.AddInstruction):
                            expr = op1 + op2
                        elif isinstance(I, ampy.types.SubInstruction):
                            expr = op1 - op2
                        elif isinstance(I, ampy.types.MulInstruction):
                            expr = op1 * op2
                        else: # new, unhandled operation
                            expr = Polynomial(I.target)
                    
                    elif isinstance(I, ampy.types.ReadInstruction):
                        expr = Polynomial(I.target)

                    else:
                        # other instructions are not considered / handled
                        continue

                    if self._mode == "poly" or expr.is_constant():
                        value = lookup.setdefault(expr, expr)
                    else:
                        value = lookup.setdefault(expr, Polynomial(I.target))

                    if value != vn.get(I.target, None):
                        changed = True
                        vn[I.target] = value
                        ampy.debug.print(self.ID, f"{I.target} updated to {value}")
            
            if not changed:
                break

        # Step 3. Collapse value number classes
        # -------------------------------------
        # vnrep[value]: representative variable for value number
        ampy.debug.print(self.ID, "Value numbering complete")
        vnrep = {}
        for var, val in vn.items():
            ampy.debug.print(self.ID, var, "=", val)
            if val.is_constant():
                vnrep[val] = str(val.constant())
            else:
                vnrep.setdefault(val, var)

        defined = set() # ensure variables are only defined once
        for block in reversed(postorder):
            to_delete = []
            for i, I in enumerate(block):
                if self._replace_or_elim(I, vn, vnrep, defined):
                    to_delete.append(i)
            for i in reversed(to_delete):
                block._instructions.pop(i)

        return tuple(opt for opt in self.opts if isinstance(opt, (RPO, SSA)))

    @(Syntax(object, ampy.types.InstructionClass, dict, dict, set) >> bool)
    def _replace_or_elim(self, I, vn, vnrep, defined):
        """
        Replaces variables with their value class representative.
        If the instruction attempts to redefine a variable, or
        attempts to define a constant, then return True to indicate
        that instruction should be deleted
        """
        def sub(v):
            if v in vn:
                return vnrep[vn[v]]
            return v

        is_def = False
        if isinstance(I, (ampy.types.ArithInstructionClass, ampy.types.CompInstructionClass)):
            I.operands = tuple(map(sub, I.operands))
            is_def = True
        elif isinstance(I, ampy.types.MovInstruction):
            I.operand = sub(I.operand)
            is_def = True
        elif isinstance(I, ampy.types.PhiInstruction):
            I.conds = tuple(map(
                lambda t: (sub(t[0]), t[1]), I.conds))
            is_def = True
        elif isinstance(I, ampy.types.BranchInstruction):
            I.cond = sub(I.cond)
        elif isinstance(I, ampy.types.ReadInstruction):
            is_def = True
        elif isinstance(I, ampy.types.WriteInstruction):
            I.operand = sub(I.operand)
        else: # Goto, Exit, Brk
            pass

        if is_def:
            I.target = sub(I.target)
            if not I.target.startswith('%') or I.target in defined:
                return True
            defined.add(I.target)

        return False



