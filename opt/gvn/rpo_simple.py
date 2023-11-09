"""
Simple RPO GVN
================
Goldthorpe

This implements a simple version of the RPO algorithm found
in figure 4.3 of

L.T. Simpson. 1996
    "Value-Driven Redundancy Elimination"
    PhD Thesis, Rice University
"""

from ampy.ensuretypes import Syntax
from opt.ssa import SSA
from opt.tools import Opt

import ampy.types
import ampy.debug

class RPO(Opt):
    # forward declaration
    pass

class Polynomial:
    # forward declaration
    pass

class Polynomial(Polynomial):
    """
    Formal polynomial of registers

    Monomials are sorted in lexicographical order
    """
    @(Syntax(object, str, ...) >> None)
    def __init__(self, primitive='0', /):
        self._dict = {}
        if primitive.startswith('%'):
            self._dict[primitive,] = 1
        elif (prim_int := int(primitive)) != 0:
            self._dict[()] = prim_int # constant coef

    def __repr__(self):
        s = ""
        for mon, coef in sorted(self._dict.items(), key=lambda p: p[0]):
            if coef < 0:
                s += " - "
                coef *= -1
            else:
                s += " + "

            if coef != 1:
                s += str(coef)

            if mon != ():
                s += f"({'*'.join(mon)})"

            if mon == () and coef == 1:
                s += "1"
        return s.strip()

    @(Syntax(object) >> None)
    def reduce(self):
        """
        Remove zero coefficients
        """
        for mon, coef in list(self._dict.items()):
            if coef == 0:
                del self._dict[mon]

    @(Syntax(object) >> bool)
    def is_constant(self):
        return len(self._dict) == 0 or len(self._dict) == 1 and () in self._dict

    @(Syntax(object) >> int)
    def constant(self):
        return self._dict.get((), 0)

    @(Syntax(object, Polynomial) >> Polynomial)
    def __mul__(self, other):
        res = Polynomial()
        for smon, scoef in self._dict.items():
            for omon, ocoef in other._dict.items():
                mon = tuple(sorted(smon + omon))
                res._dict[mon] = res._dict.get(mon, 0) + scoef * ocoef
        res.reduce()
        return res

    @(Syntax(object, Polynomial) >> Polynomial)
    def __add__(self, other):
        res = Polynomial()
        for smon, scoef in self._dict.items():
            res._dict[smon] = scoef
        for omon, ocoef in other._dict.items():
            res._dict[omon] = res._dict.get(omon, 0) + ocoef
        res.reduce()
        return res

    @(Syntax(object, Polynomial) >> Polynomial)
    def __sub__(self, other):
        res = Polynomial()
        for smon, scoef in self._dict.items():
            res._dict[smon] = scoef
        for omon, ocoef in other._dict.items():
            res._dict[omon] = res._dict.get(omon, 0) - ocoef
        res.reduce()
        return res

    @(Syntax(object, (Polynomial, None)) >> bool)
    def __eq__(self, other):
        if other is None:
            return False
        for mon, coef in self._dict.items():
            if other._dict.get(mon, 0) != coef:
                return False
        for mon, coef in other._dict.items():
            if self._dict.get(mon, 0) != coef:
                return False
        return True
    
    def __hash__(self):
        # lazy hash
        return hash(tuple(sorted(self._dict.items(), key=lambda v:v[0])))


class RPO(RPO):
    """
    rpo-gvn

    Runs a simple version of Simpson's RPO GVN algorithm
    """

    @RPO.init("rpo-gvn")
    def __init__(self, /):
        pass

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
        # RPO[i]: ith block in reverse post-order
        rpo = []
        
        seen = set()
        def postorder(block):
            seen.add(block)
            for child in block.children:
                if child not in seen:
                    postorder(child)
            rpo.append(block)
        
        postorder(self.CFG.entrypoint)
        rpo.reverse()

        # Step 2. Value numbering
        # -----------------------
        # Repeat value lookup until a fixedpoint is found
        vn = {}
        def vnpoly(op):
            if op.startswith('%'):
                return vn.get(op, Polynomial('%?'))
            return Polynomial(op)

        while True:
            lookup = {}
            changed = False
            for block in rpo:
                for I in block:
                    if isinstance(I, ampy.types.PhiInstruction):
                        if len(set(vnpoly(val) for val, _ in I.conds)) == 1:
                            vn[I.target] = vnpoly(I.conds[0][0])
                        else:
                            vn[I.target] = Polynomial(I.target)
                    if isinstance(I, ampy.types.ReadInstruction):
                        # reads cannot be handled optimistically
                        vn[I.target] = Polynomial(I.target)

                    if isinstance(I, ampy.types.MovInstruction):
                        vn[I.target] = vnpoly(I.operand)

                    if not isinstance(I, ampy.types.ArithInstructionClass):
                        # we do not process non-arithmetic instructions
                        continue
                    op1, op2 = map(vnpoly, I.operands)
                    if isinstance(I, ampy.types.AddInstruction):
                        expr = op1 + op2
                    elif isinstance(I, ampy.types.SubInstruction):
                        expr = op1 - op2
                    else: # multiplication
                        expr = op1 * op2

                    if expr.is_constant():
                        value = expr
                    else:
                        value = lookup.setdefault(expr, Polynomial(I.target))
                    if value != vn.get(I.target, None):
                        changed = True
                        vn[I.target] = value
            
            if not changed:
                break

        # Step 3. 
        # -----------------------------------------------
        # vnrep[value]: representative variable for value number
        vnrep = {}
        for var, val in vn.items():
            ampy.debug.print(self.ID, var, "=", val)
            if val.is_constant():
                vnrep[val] = str(val.constant())
            else:
                vnrep.setdefault(val, var)

        defined = set() # SSA
        for block in rpo:
            to_delete = []
            for i, I in enumerate(block):
                if self._replace_or_elim(I, vn, vnrep, defined):
                    to_delete.append(i)
            for i in reversed(to_delete):
                block._instructions.pop(i)

        return tuple(opt for opt in self.opts if isinstance(opt, RPO))

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



