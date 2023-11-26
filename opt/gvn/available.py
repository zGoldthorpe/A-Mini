"""
Availability analysis
=======================
Goldthorpe

Implements available expression flow analysis from Fig. 6.3 of

L.T. Simpson. 1996
    "Value-Driven Redundancy Elimination"
    PhD Thesis, Rice University
"""

from utils.syntax import Syntax

from opt.tools import Opt

from opt.gvn.expr import Expr
from opt.gvn.simpson import RPO, SCC

from ampy.passmanager import BadArgumentException
import ampy.types

class AvailAnalysis(Opt):
    # forward declaration
    pass

class AvailAnalysis(AvailAnalysis):
    """
    Availability analysis

    Indicates at each block and instruction which expressions are available
    for use, where expressions are identified by their value numbers.
    An expression is available at a point P if the expression is defined prior
    to P along all possible paths of execution leading to P.

    gvn: "rpo" or "scc" or "any"
        Identify which GVN algorithm to use
    """

    @AvailAnalysis.init("available", gvn="any")
    def __init__(self, *, gvn):
        if gvn not in ("rpo", "scc", "any"):
            raise BadArgumentException("`gvn` must be one of \"rpo\", \"scc\", or \"any\".")
        self._gvn = RPO if gvn == "rpo" else SCC if gvn == "scc" else (RPO, SCC)

    @AvailAnalysis.getter
    @(Syntax(object, ampy.types.BasicBlock)
      | Syntax(object, ampy.types.BasicBlock, int)
      >> [Expr])
    def avail_in(self, block, idx=None, /):
        """
        Give the list of available expressions coming into a block or instruction.
        """
        if idx is None:
            ls = self.get(block, "in", default=[])
        else:
            ls = self.get(block, idx, "in", default=[])

        i = 0
        ret = []
        while i < len(ls):
            expr, i = Expr.read_polish_ls(ls, i)
            ret.append(expr)
        return ret

    @AvailAnalysis.getter
    @(Syntax(object, ampy.types.BasicBlock)
      | Syntax(object, ampy.types.BasicBlock, int)
      >> [Expr])
    def avail_out(self, block, idx=None, /):
        """
        Give the list of available expressions coming out of a block or instruction.
        """
        if idx is None:
            ls = self.get(block, "out", default=[])
        else:
            ls = self.get(block, idx, "out", default=[])

        i = 0
        ret = []
        while i < len(ls):
            expr, i = Expr.read_polish_ls(ls, i)
            ret.append(expr)
        return ret

    @AvailAnalysis.opt_pass
    def flow_analysis(self):
        # Step 0. Compute value numbers
        # -----------------------------
        gvn = self.require(self._gvn, "expr")
        self._vn = gvn.get_value_partitions()

        # Step 1. Find available expressions
        # ----------------------------------
        # The set of available expressions is computed via flow analysis:
        #
        # av_in[I] = Intersect(av_out[J] for J preceding I)
        # av_out[I] = av_in[I] + defs[I]
        #
        # where defs[I] is the set of expressions computed in I
        self._av_in = {}
        self._av_out = {}

        flow = True
        postorder = self.CFG.postorder
        while flow:
            self.debug("running flow analysis")
            flow = False
            for block in postorder:
                # deal with first instruction
                av_in = set()
                if len(block.parents) > 0:
                    parents = list(block.parents)
                    av_in = set(self._av_out.get(parents[0], set()))
                    for i in range(1, len(parents)):
                        av_in &= self._av_out.get(parents[i], set())
                if av_in != self._av_in.setdefault((block, 0), set()):
                    flow = True
                    self._av_in[block, 0] = av_in
                if ((av_out := av_in | self._defset(block[0]))
                        != self._av_out.setdefault((block, 0), set())):
                    flow = True
                    self._av_out[block, 0] = av_out

                # now for the remaining instructions
                for i in range(1, len(block)):
                    if ((av_in := self._av_out[block, i-1])
                            != self._av_in.setdefault((block, i), set())):
                        flow = True
                        self._av_in[block, i] = set(av_in)
                    if ((av_out := av_in | self._defset(block[i]))
                            != self._av_out.setdefault((block, i), set())):
                        flow = True
                        self._av_out[block, i] = av_out

                # now summarise the flow analysis for the blocks
                self._av_in[block] = self._av_in[block, 0]
                self._av_out[block] = self._av_out[block, len(block)-1]

        # Step 2. Record flow analysis results
        # ------------------------------------
        for block in self.CFG:
            self.assign(block, "in", *(expr.polish for expr in self._av_in[block]))
            self.assign(block, "out", *(expr.polish for expr in self._av_out[block]))
            for i in range(len(block)):
                self.assign(block, i, "in", *(expr.polish for expr in self._av_in[block, i]))
                self.assign(block, i, "out", *(expr.polish for expr in self._av_out[block, i]))

        # this is an analysis pass
        return self.opts

    @(Syntax(object, str) >> Expr)
    def _get_vn(self, var):
        return self._vn.get(var, Expr(var))

    @(Syntax(object, ampy.types.InstructionClass) >> [set, Expr])
    def _defset(self, I):
        if isinstance(I, ampy.types.DefInstructionClass):
            return {self._get_vn(I.target)}
        return set()
