"""
Simple RPO GVN
================
Goldthorpe

This implements a version of the RPO algorithm found
in figure 4.3 Simpson's PhD Thesis.

L.T. Simpson. 1996
    "Value-Driven Redundancy Elimination"
    PhD Thesis, Rice University
"""

from utils.syntax import Syntax

from opt.tools import Opt, OptError
from opt.ssa import SSA
from opt.gvn.abstract_expr import Expr

from ampy.passmanager import BadArgumentException
import ampy.types

class RPO(Opt):
    # forward declaration
    pass

class RPO(RPO):
    """
    Runs a GVN algorithm based on Simpson's RPO algorithm

    number: "var" or "expr"
        If "var", then value numbers are given by registers or constants.
        If "expr", then value numbers are given by expressions.
    """

    @RPO.init("gvn-rpo", "var")
    def __init__(self, number, /):
        if number not in ("var", "expr"):
            raise BadArgumentException("Mode must be one of \"simple\" or \"poly\".")
        self._number = number

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
        postorder = self.CFG.postorder

        # Step 2. Value numbering
        # -----------------------
        # Repeat value lookup until a fixedpoint is found
        vn = {}
        def get_vn(var):
            if var.startswith('%'):
                return vn.get(var, Expr('?'))
            return Expr(int(var))

        while True:
            self.debug("Updating value numbers")
            lookup = {}
            changed = False
            for block in reversed(postorder):
                for I in block:
                    if isinstance(I, ampy.types.MovInstruction):
                        expr = get_vn(I.operand)
                    elif isinstance(I, ampy.types.PhiInstruction):
                        args = []
                        for val, label in I.conds:
                            args.append(get_vn(val))
                            args.append(Expr(label))
                        expr = Expr(type(I), *args)
                    elif isinstance(I, ampy.types.BinaryInstructionClass):
                        op1, op2 = map(get_vn, I.operands)
                        expr = Expr(type(I), op1, op2)
                    elif isinstance(I, ampy.types.DefInstructionClass):
                        # unhandled definition class, so cannot be optimistic
                        # (e.g., reads)
                        expr = Expr(I.target)
                    else:
                        # we do not handle non-def instructions
                        continue

                    if ((self._number == "expr" and
                            expr.op != ampy.types.PhiInstruction)
                            or isinstance(expr.op, (int, str))):
                        # do not expand phi instructions as expressions
                        # or else you will face infinite loops
                        value = lookup.setdefault(expr, expr)
                    else:
                        value = lookup.setdefault(expr, Expr(I.target))

                    if I.target not in vn or value != vn[I.target]:
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
            if isinstance(val.op, int):
                vnclasses[val].add(str(val.op)) # include constant if known

        self.assign("classes")
        for _, vnclass in vnclasses.items():
            self.assign("classes", *sorted(vnclass), append=True)
            self.assign("classes", '$', append=True)

        return self.opts

    @RPO.getter
    @(Syntax(object) >> {str:(str,int)})
    def get_value_partitions(self):
        """
        Returns a mapping from variable names to "value numbers".
        If the VN class corresponds to an integer, then all variables will
        map to this integer; otherwise, they will map to a selected
        representative variable from the VN class (as a string).
        """
        ret = {}
        cls = []
        rep = None
        for var in self["classes"]:
            if var == '$':
                for v in cls:
                    ret[v] = rep
                rep = None
                cls = []
                continue
            if not var.startswith('%'):
                # this is a constant
                rep = int(var)
                continue
            if rep is None:
                rep = var
            cls.append(var)
        return ret
