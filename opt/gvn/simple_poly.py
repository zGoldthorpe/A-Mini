"""
Simple polynomial 
===================
Goldthorpe

This provides a simple polynomial type for handling abstract
polynomial expressions of registers.
"""

from ampy.ensuretypes import Syntax

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
                s += " + " if len(s) > 0 else ""

            if coef != 1:
                s += str(coef)

            if mon != ():
                s += f"({'*'.join(mon)})"

            if mon == () and coef == 1:
                s += "1"
        s = s.strip()
        if len(s) > 0:
            return s
        return "0"

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

