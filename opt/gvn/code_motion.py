"""
Value-driven code motion
==========================
Goldthorpe

Implements a version of VDCM as described in section 7.1 of

L.T. Simpson. 1996
    "Value-Driven Redundancy Elimination"
    PhD Thesis, Rice University
"""

from utils.syntax import Syntax

from opt.tools import Opt, OptError

from opt.analysis.domtree import DomTreeAnalysis

from opt.gvn.expr import Expr
from opt.gvn.anticipatable import Anticipate
from opt.gvn.simpson import RPO, SCC

from ampy.passmanager import BadArgumentException
import ampy.types

class VDCM(Opt):
    # forward declaration
    pass

class VDCM(VDCM):
    """
    Value-driven code motion

    Reorganises computations of expressions in an attempt to minimise
    (partial) redundancy via value-based lazy code motion described
    in Simpson's PhD Thesis.
    """
    
    @VDCM.init("vdcm", gvn="any")
    def __init__(self, *, gvn):
        if gvn not in ("rpo", "scc", "any"):
            raise BadArgumentException("`gvn` must be one of \"rpo\", \"scc\", or \"any\".")
        self._gvnarg = gvn
        self._gvn = RPO if gvn == "rpo" else SCC if gvn == "scc" else (RPO, SCC)


    @VDCM.opt_pass
    def lazy_code_motion(self):
        # Step 0. Get value numbering and anticipatability
        # ------------------------------------------------
        self._vn = self.require(self._gvn, "expr").get_value_partitions()
        antic = self.require(Anticipate, gvn=self._gvnarg)
        earliest = {}
        for block in self.CFG:
            for child in block.children:
                earliest[block, child] = antic.earliest(block, child)
                self.debug("earliest", block.label, child.label, ":", ", ".join(str(expr) for expr in earliest[block, child]))

        # Step 1. Determine where expressions can be delayed
        # --------------------------------------------------
        # An expression can be delayed to after B if it can be delayed
        # to after all predecessors of B, and B does not define any of its
        # subexpressions.
        # Lateness can be computed via flow analysis:
        #
        # later_in[B] = Intersect(later[P, B] for P preceding B)
        # later[B, C] = (later_in[B] - alt[B]) + earliest[B, C]
        defs = {}
        alts = {}
        all_exprs = set()
        for block in self.CFG:
            defset = set()
            for I in block:
                if isinstance(I, ampy.types.DefInstructionClass):
                    vn = self._vn.get(I.target, Expr(I.target))
                    all_exprs.add(vn)
                    defset.add(vn)
            defs[block] = defset
            alts[block] = set(antic.altered(block))

        postorder = self.CFG.postorder
        later = {}
        flow = True
        while flow:
            self.debug("Performing lateness flow analysis")
            flow = False
            for block in reversed(postorder):
                later_in = set(all_exprs)
                for parent in block.parents:
                    later_in &= later.setdefault((parent, block), all_exprs)
                if later_in != later.setdefault(block, set()):
                    flow = True
                    later[block] = later_in

                blockdefs = defs[block] - alts[block]
                for child in block.children:
                    if ((later_out := (later_in - blockdefs) | earliest[block, child])
                            != later.setdefault((block, child), set())):
                        flow = True
                        later[block, child] = later_out

        for key, exprs in sorted(later.items(), key=lambda p: p[0].label if not isinstance(p[0], tuple) else p[0][0].label):
            if isinstance(key, ampy.types.BasicBlock):
                self.debug("later", key.label,":", ", ".join(str(expr) for expr in exprs))
            else:
                self.debug("later", key[0].label, key[1].label, ":", ", ".join(str(expr) for expr in exprs))

        # Step 2. Determine insertion and deletion points
        # -----------------------------------------------
        # Insert an expression at B -> C if the expression can be delayed
        # until B -> C, but cannot be delayed further.
        #
        # Delete an expression from B if it its computation from the entrypoint
        # cannot be delayed to just before B, as this would mean that the
        # expression computation at B is necessary.
        #
        # insert[B, C]: set of expressions to insert between B and C
        # insert[B]: set of expressions to insert at the end of B
        # delete[B]: set of expressions to remove from B

        self._insert = {}
        self._delete = {}
        def keep(expr):
            # do not move or delete constants or phi nodes
            return not isinstance(expr.op, (int, str)) and expr.op != ampy.types.PhiInstruction
        for block in self.CFG:
            self._delete[block] = set(filter(keep,
                    defs[block] - set(antic.altered(block)) - later.get(block, set())))
            self.debug(block.label, "delete", ", ".join(str(expr) for expr in self._delete[block]))
            children = list(block.children)
            if len(children) == 0:
                continue

            self._insert[block] = set(filter(keep,
                    later.get((block, children[0]), set())
                        - later.get(children[0], set())))
            if len(children) > 1:
                self._insert[block, children[0]] = self._insert[block] & set(antic.ant_in(children[0]))
                next_insert = set(filter(keep,
                    later.get((block, children[1]), set())
                        - later.get(children[1], set()))) & set(antic.ant_in(children[1]))
                self._insert[block, children[1]] = next_insert
                self._insert[block] &= next_insert

                self._insert[block, children[0]] -= self._insert[block]
                self._insert[block, children[1]] -= self._insert[block]
            self._insert[block] &= set(antic.ant_out(block))


        # Step 3. Split critical edges
        # ----------------------------
        # Some insertion points may be along edges between
        # basic blocks (namely, when a block with multiple children
        # maps into a block with multiple parents). We resolve
        # these by inserting new basic blocks where necessary.
        changed_cfg = False
        for key in list(self._insert.keys()):
            if isinstance(key, ampy.types.BasicBlock):
                # insertions in insert[B] can be made at the end
                # of the block B
                self.debug(key.label, "insert", ", ".join(str(expr) for expr in self._insert[key]))
                continue
            block, child = key
            inserts = self._insert.pop(key)
            if len(inserts) == 0:
                continue
            crit = self._insert_block(block, child)
            self._insert[crit] = inserts
            self.debug(crit.label, "insert", ", ".join(str(expr) for expr in inserts))
            changed_cfg = True

        if changed_cfg:
            # if the dominator tree has been computed before,
            # it is no longer valid
            self.require(DomTreeAnalysis).valid = False

        # Step 4. Make insertions and deletions
        # -------------------------------------
        # We make substitutions by traversing the dominator tree
        # depth-first, and decide representatives as we go.
        #
        # NB. Code motion breaks SSA form, but not completely!
        # Value numbers will correspond to unique registers, but may
        # be defined in several places.
        self._changed = False
        self._dommem = {} # memoisation for substitutions
        self._reg = 0 # for new registers

        self.vnrep = {} # value number representative registers
        for var, expr in self._vn.items():
            if isinstance(expr.op, int):
                self.vnrep[expr] = str(expr.op)
            else:
                self.vnrep.setdefault(expr, var)

        self._dfs_and_sub(self.CFG.entrypoint)

        # Step 5. Adjust phi nodes
        # ------------------------
        # Although not in SSA form, phi nodes will likely remain.
        # Ensure that phi node arguments coming from back-edges are
        # correct, and avoid register conflicts in phi node definitions.
        for block in self.CFG:
            assigns = set()
            for i, I in enumerate(block):
                if isinstance(I, ampy.types.PhiInstruction):
                    conds = []
                    for val, label in I.conds:
                        vn = self._vn.get(val, Expr(val))
                        if isinstance(vn.op, int):
                            reg = str(vn.op)
                        else:
                            reg = self.vnrep[vn]
                        if reg in assigns:
                            # the phi node relies on a register defined
                            # earlier in the same block
                            # so copy the intended value in corresponding
                            # predecessor
                            self._changed = True
                            new = self._new_register(vn)
                            self.CFG[label]._instructions.insert(-1,
                                    ampy.types.MovInstruction(new, reg))
                            reg = new

                        conds.append((reg, label))

                    I.conds = tuple(conds) # rebuild phi node
                
                if isinstance(I, ampy.types.DefInstructionClass):
                    assigns.add(I.target)

        if changed_cfg and self._changed:
            return tuple(filter(lambda opt: opt.ID == "vdcm", self.opts))
        if changed_cfg:
            return tuple(filter(lambda opt: opt.ID in ("vdcm", "ssa"), self.opts))
        if self._changed:
            return tuple(filter(lambda opt: opt.ID in ("vdcm", "domtree"), self.opts))
        return self.opts

    @(Syntax(object, Expr, ampy.types.BasicBlock) >> (str, None))
    def _get_dominating_var(self, expr, block):
        """
        Returns the dominating definition of an expression, or None
        if this value number class has not been defined yet along this
        path in the dominator tree.
        """
        if isinstance(expr.op, int):
            return str(expr.op)
        if expr not in self._dommem.setdefault(block, {}):
            if block == self.CFG.entrypoint:
                # this means the variable has never been defined
                # in this path along the dominator tree
                self._dommem[block][expr] = None
            else:
                # walk up dominating tree until you find its definition
                idom = self.require(DomTreeAnalysis).idom(block)
                self._dommem[block][expr] = self._get_dominating_var(expr, idom)

        return self._dommem[block][expr]

    @(Syntax(object, ampy.types.BasicBlock) >> None)
    def _dfs_and_sub(self, block):
        """
        Depth-first traversal of dominator tree
        """
        def sub(var):
            expr = self._vn.get(var, Expr(var))
            ret = self._get_dominating_var(expr, block)
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
                if vn in self._delete.get(block, set()):
                    # we have opted to remove this expression
                    to_delete.append(i)
                    continue
                rep = self._get_dominating_var(vn, block)
                if rep is None:
                    # value has not been computed yet
                    I.target = self.vnrep[vn]
                    self._dommem[block][vn] = I.target
                    continue
                # otherwise, value has already been computed
                # so this definition is redundant
                to_delete.append(i)
    
        self._changed |= len(to_delete) > 0
        for i in reversed(to_delete):
            block._instructions.pop(i)

        # now, handle insertions
        for expr in self._insert.get(block, set()):
            res = self._insert_expr(block, expr)

        for child in self.require(DomTreeAnalysis).children(block):
            self._dfs_and_sub(child)

    @(Syntax(object, ampy.types.BasicBlock, Expr) >> str)
    def _insert_expr(self, block, expr):
        """
        Insert a definition of an expression at the end of the block.
        Returns the variable storing the expression.
        """
        var = self._get_dominating_var(expr, block)
        if var is not None:
            # expression has already been defined before this point
            return var
        # otherwise, we are inserting a new instruction
        self._changed = True

        if isinstance(expr.op, (int, str)):
            return str(expr.op)

        # build expression operands
        op, (left, right) = expr.recipe
        lhs = self._insert_expr(block, left)
        rhs = self._insert_expr(block, right)

        # finally, build the expression and register it as dominating
        target = self.vnrep.get(expr, None)
        if target is None:
            target = self._new_register(expr)
        block._instructions.insert(-1, op(target, lhs, rhs))
        self._dommem[block][expr] = target
        return target

    @(Syntax(object, ampy.types.BasicBlock, ampy.types.BasicBlock) >> ampy.types.BasicBlock)
    def _insert_block(self, block, child):
        """
        Insert a new basic block between block and child, and
        return the block.
        (Assumes child is really a child of the block.)
        """
        anon = 0
        while (label := f"@.{anon}") in self.CFG.labels:
            anon += 1

        if len(set(block.children)) == 2:
            cond = block.branch_instruction.cond
            istrue = child.label == block.branch_instruction.iftrue
        else:
            cond = None
    
        self.CFG.create_block(label)
        newblock = self.CFG[label]

        block.remove_child(child) # keep duplicate is False by default
        if cond is not None:
            block.add_child(newblock, cond=cond, new_child_if_cond=istrue)
        else:
            block.add_child(newblock)

        newblock.add_child(child)
        # correct child's phi nodes
        for I in child:
            if isinstance(I, ampy.types.PhiInstruction):
                I.conds = tuple(
                        (val, label if label != block.label else newblock.label)
                        for val, label in I.conds)
        return newblock
    
    @(Syntax(object, Expr) >> str)
    def _new_register(self, value):
        while (var := f"%.{self._reg}") in self._vn:
            self._reg += 1
        self._vn[var] = value
        return var
