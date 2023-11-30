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

from opt.gvn.expr import Expr
from opt.gvn.available import AvailAnalysis
from opt.gvn.simpson import RPO, SCC
from opt.gvn.gargi import GVN

from ampy.passmanager import BadArgumentException
import ampy.types

class Anticipate(Opt):
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

class Anticipate(Anticipate):
    __doc__ = f"""
    Anticipatability analysis
    
    Indicates at each block and instruction which expressions are anticipatable,
    where expressions are identified with their value numbers.
    An expression is "anticipatable" at a point P if it eventually becomes
    available along any path out of P, and definitions of this expression can
    be placed anywhere along these paths.

    gvn: {acc_str}
        Identify which GVN algorithm to use
    """

    @Anticipate.init("anticipatable", gvn="any")
    def __init__(self, *, gvn):
        if gvn not in acc:
            raise BadArgumentException(f"`gvn` must be one of {acc_str}")
        self._gvnarg=gvn
        self._gvn, self._args = acc[gvn]

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

    @Anticipate.getter
    @(Syntax(object, ampy.types.BasicBlock) >> [Expr])
    def altered(self, block):
        """
        Give the list of altered expressions at a block, where an expression
        is altered if one of its subexpressions is defined in this block for
        the first time along some execution path from the entrypoint.
        """
        ls = self.get(block, "alt", default=[])
        i = 0
        ret = []
        while i < len(ls):
            expr, i = Expr.read_polish_ls(ls, i)
            ret.append(expr)
        return ret

    @Anticipate.getter
    @(Syntax(object, ampy.types.BasicBlock, ampy.types.BasicBlock) >> [set, Expr])
    def earliest(self, block, child):
        """
        Compute the set of expressions that are earliest along the edge from
        the block to its child.
        
        An expression is "earliest" on B -> C if it can be computed at this
        point, and such a computation would be the first time this value is
        computed along any execution path from the entrypoint to B -> C.

        NB: this is only meaningful if child is a child of the block.
        """
        # earliest[B, C] = (ant_in[C] - av_out[B] - ant_out[B]) +
        #                   ((ant_in[C] - av_out[B]) & alt[B])
        early = set(self.ant_in(child))
        early -= set(self.require(AvailAnalysis).avail_out(block))

        return (early & set(self.altered(block))) | (early - set(self.ant_out(block)))

    @Anticipate.opt_pass
    def flow_analysis(self):
        # Step 0. Get value numbers and available expressions
        # ---------------------------------------------------
        self._vn = self.require(self._gvn, *self._args).get_value_partitions()
        avail = self.require(AvailAnalysis, gvn=self._gvnarg)

        # Step 1. Track altered expressions
        # ---------------------------------
        # alt[B] represents the set of expressions that cannot be moved up
        #       past B because one of its operands is defined in B.
        #       More precisely, it is the set of expressions that contain
        #       a subexpression that is defined for the first time in B along
        #       some execution path.
        #
        # Based on Simpson, Fig. 7.1.
        #
        # To determine if an expression's operand is altered, we need to first collect
        # all expressions, and associate them with the corresponding global value numbers
        expr_set = {}
        expr_deps = {}
        for block in self.CFG:
            for I in block:
                if isinstance(I, ampy.types.DefInstructionClass):
                    vn = self._vn.get(I.target, Expr(I.target))
                    expr_deps.setdefault(vn, set())

                    if isinstance(I, ampy.types.PhiInstruction):
                        for val, _ in I.conds:
                            expr_deps[vn].add(self._vn.get(val, Expr(val)))
                    elif isinstance(I, ampy.types.BinaryInstructionClass):
                        expr_deps[vn] |= set(map(lambda op: self._vn.get(op, Expr(op)), I.operands))
        
        self._alt = {}
        for block in self.CFG:
            for i, I in enumerate(block):
                if not isinstance(I, ampy.types.DefInstructionClass):
                    self._alt[block, i] = set()
                    continue
                alt = set()
                vn = self._vn.get(I.target, Expr(I.target))
                for expr, deps in expr_deps.items():
                    if vn in deps or len(alt & deps) > 0:
                        alt.add(expr)
                self._alt[block, i] = alt

        # Step 2. Compute anticipatable values
        # ------------------------------------
        # Anticipatability is computed via flow analysis:
        #
        # ant_out[B] = Intersect(ant_in[C] for C succeeding B)
        # ant_in[B] = (ant_out[B] - alt[B]) + defs[B]
        #
        # where defs[B] is the set of expressions generated by B

        self._ant_out = {}
        self._ant_in = {}
        postorder = self.CFG.postorder
        flow = True
        while flow:
            self.debug("running flow analysis")
            flow = False
            for block in reversed(postorder):
                # deal with branch instruction first
                br = len(block)-1
                match len(block.children):
                    case 1:
                        ant_out = set(self._ant_in.get(block.children[0], set()))
                    case 2:
                        ant_out = self._ant_in.get(block.children[0], set()) & self._ant_in.get(block.children[1], set())
                    case _:
                        ant_out = set()
                if ant_out != self._ant_out.setdefault((block, br), set()):
                    flow = True
                    self._ant_out[block, br] = ant_out
                if ((ant_in := (ant_out - self._alt[block, br]))
                        != self._ant_in.setdefault((block, br), set())):
                    flow = True
                    self._ant_in[block, br] = ant_in

                # now the remaining instructions
                for i in range(len(block)-2, -1, -1):
                    I = block[i]
                    if ((ant_out := self._ant_in[block, i+1])
                            != self._ant_out.setdefault((block, i), set())):
                        flow = True
                        self._ant_out[block, i] = ant_out
                    ant_in = set(ant_out)
                    if isinstance(I, ampy.types.DefInstructionClass):
                        ant_in.add(self._vn.get(I.target, Expr(I.target)))
                    ant_in -= self._alt[block, i]
                    if ant_in != self._ant_in.setdefault((block, i), set()):
                        flow = True
                        self._ant_in[block, i] = ant_in

                # now summarise the results for the block
                self._ant_out[block] = self._ant_out[block, len(block)-1]
                self._ant_in[block] = self._ant_in[block, 0]

        # Step 3. Record flow analysis results
        # ------------------------------------
        for block in postorder:
            self.assign(block, "in", *(expr.polish for expr in self._ant_in[block]))
            self.assign(block, "out", *(expr.polish for expr in self._ant_out[block]))
            altset = set()
            for i in range(len(block)):
                self.assign(block, i, "alt", *(expr.polish for expr in self._alt[block, i]))
                self.assign(block, i, "in", *(expr.polish for expr in self._ant_in[block, i]))
                self.assign(block, i, "out", *(expr.polish for expr in self._ant_out[block, i]))
                altset |= self._alt[block, i]

            self.assign(block, "alt", *(expr.polish for expr in altset))

        # this is an analysis pass
        return self.opts
        

    @(Syntax(object, str) >> Expr)
    def _get_vn(self, var):
        return self._vn.get(var, Expr(var))


