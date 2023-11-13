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

from utils.syntax import Syntax

from opt.tools import Opt
from opt.ssa import SSA
from opt.gvn.simple_poly import Polynomial

from ampy.passmanager import BadArgumentException
import ampy.types

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
            self.debug("Updating value numbers")
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

                    elif isinstance(I, ampy.types.DefInstructionClass):
                        # cannot be optimistic about unhandled definition
                        # instructions (such as reads)
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
                        self.debug(f"{I.target} updated to {value}")
            
            if not changed:
                break

        # Step 3. Print value number classes
        # ----------------------------------
        self.debug("Value numbering complete")
        vnclasses = {}
        for var, val in vn.items():
            vnclasses.setdefault(val, set()).add(var)
            if val.is_constant():
                vnclasses[val].add(str(val.constant())) # include constant if known

        self.assign("classes")
        for _, vnclass in vnclasses.items():
            self.assign("classes", *sorted(vnclass), append=True)
            self.assign("classes", '$', append=True)

        return self.opts

