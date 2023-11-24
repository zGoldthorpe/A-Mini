"""
Anticipatability analysis
===========================
Golthorpe

Implements anticipated expression flow analysis from Fig. 6.3. of

L.T. Simpson. 1996
    "Value-Driven Redundancy Elimination"
    PhD Thesis, Rice University
"""

from utils.syntax import Syntax

from opt.tools import Opt

from opt.gvn.abstract_expr import Expr
from opt.gvn.available_expr import AvailAnalysis
from opt.gvn.simpson import RPO, SCC

from ampy.passmanager import BadArgumentException
import ampy.types

class Anticipate(Opt):
    # forward declaration
    pass

class Anticipate(Anticipate):
    """
    Anticipatability analysis
    
    Indicates at each block and instruction which expressions are anticipatable,
    where expressions are identified with their value numbers.
    An expression is "anticipatable" at a point P if it is available at P, and
    all paths out of P will use the expression.

    gvn: "rpo" or "scc" or "any"
        Identify which GVN algorithm to use
    """

    @Anticipate.init("anticipatable", gvn="any")
    def __init__(self, *, gvn):
        if gvn not in ("rpo", "scc", "any"):
            raise BadArgumentException("`gvn` must be one of \"rpo\", \"scc\", or \"any\".")
        self._gvnarg = gvn
        self._gvn = RPO if gvn == "rpo" else SCC if gvn == "scc" else (RPO, SCC)

    @Anticipate.getter
    @(Syntax(object, ampy.types.BasicBlock) >> [Expr])
    def ant_in(self, block):
        """
        Give the list of anticipatable expressions coming into a block
        """
        ls = self.get(block, "in", default=[])
        i = 0
        ret = []
        while i < len(ls):
            expr, i = Expr.read_polish_ls(ls, i)
            ret.append(expr)
        return ret

    @Anticipate.getter
    @(Syntax(object, ampy.types.BasicBlock) >> [Expr])
    def ant_out(self, block):
        """
        Give the list of anticipatable expressions coming out of a block
        """
        ls = self.get(block, "out", default=[])
        i = 0
        ret = []
        while i < len(ls):
            expr, i = Expr.read_polish_ls(ls, i)
            ret.append(expr)
        return ret

    @Anticipate.opt_pass
    def flow_analysis(self):
        # Step 0. Get value numbers and available expressions
        # ---------------------------------------------------
        self._vn = self.require(self._gvn, "expr").get_value_partitions()
        avail = self.require(AvailAnalysis, gvn=self._gvnarg)

        # Step 1. Track altered expressions
        # ---------------------------------
        # alt[B] represents the set of expressions that cannot be moved up
        # past B because one of its operands is defined in B
        #
        # Based on Simpson, Fig. 7.1.
        subexpr_trees = [(expr, list(expr.subexpressions))
                            for expr in set(self._vn.values())]
        self._alt = {}
        for block in self.CFG:
            alt = set(avail.avail_out(block)) - set(avail.avail_in(block))
            if len(alt) > 0:
                for expr, tree in subexpr_trees:
                    if expr in alt:
                        continue
                    for subexpr in tree:
                        if subexpr in alt:
                            alt.add(expr)
                            break
            self._alt[block] = alt

        # Step 2. Compute anticipatable values
        # ------------------------------------
        # Anticipatability is computed via flow analysis:
        #
        # ant_out[B] = Intersect(ant_in[C] for C succeeding B)
        # ant_in[B] = (ant_out[B] + defs[B]) - alt[B]
        #
        # where defs[B] is the set of expressions generated by B
        defs = {}
        for block in self.CFG:
            defset = set()
            for I in block:
                if isinstance(I, ampy.types.DefInstructionClass):
                    defset.add(self._vn.get(I.target, Expr(I.target)))
            defs[block] = defset

        self._ant_out = {}
        self._ant_in = {}
        postorder = self.CFG.postorder
        flow = True
        while flow:
            self.debug("running flow analysis")
            flow = False
            for block in reversed(postorder):
                match len(block.children):
                    case 1:
                        ant_out = set(self._ant_in.get(block.children[0], set()))
                    case 2:
                        ant_out = self._ant_in.get(block.children[0], set()) & self._ant_in.get(block.children[1], set())
                    case _:
                        ant_out = set()
                if ant_out != self._ant_out.setdefault(block, set()):
                    flow = True
                    self._ant_out[block] = ant_out
                if ((ant_in := (ant_out | defs[block]) - self._alt[block])
                        != self._ant_in.setdefault(block, set())):
                    flow = True
                    self._ant_in[block] = ant_in

        # Step 3. Record flow analysis results
        # ------------------------------------
        for block in postorder:
            self.assign(block, "in", *(expr.polish for expr in self._ant_in[block]))
            self.assign(block, "out", *(expr.polish for expr in self._ant_out[block]))

        # this is an analysis pass
        return self.opts
        

    @(Syntax(object, str) >> Expr)
    def _get_vn(self, var):
        return self._vn.get(var, Expr(var))


