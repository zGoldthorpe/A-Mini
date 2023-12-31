"""
Gargi GVN algorithm
=====================
Goldthorpe

Implements a version of the GVN algorithm described in

K. Gargi. 2002
    "A Sparse Algorithm for Predicated Global Value Numbering"
    PLDI'02
    Pages 45--56.
"""

import heapq

from utils.syntax import Syntax

from opt.tools import Opt, OptError
from opt.ssa import SSA
from opt.analysis.djgraph import DJGraph
from opt.gvn.expr import Expr
from opt.gvn.predicates import PredicatedState

from ampy.passmanager import BadArgumentException
import ampy.types

class GVN(Opt):
    # forward declaration
    pass

class GVN(GVN):
    """
    Runs a variant of Gargi's GVN algorithm.

    i: int
        Indicate number of bits used for integers. Use 0 for infinite bits, or
        -1 for the default established by an earlier pass.
        (default: -1)
    """

    @GVN.init("gargi-gvn", i="-1")
    def __init__(self, *, i):
        try:
            i = int(i)
        except ValueError:
            raise BadArgumentException("`i` must be an integer.")
        if i >= 0:
            Expr.intsize = i
    

    @GVN.opt_pass
    def gvn(self):
        """
        Global value numbering
        """
        # Step 0. Preprocessing
        # ---------------------
        #
        # touched: a heap of pairs (rpo_num, idx)
        #          - rpo_num: RPO number of a block
        #          - idx: index of instruction in block, or -1 for block itself
        # reachable: reachability graph, mimics the nodes of the true CFG
        # DJ: DJ-graph for the reachable subgraph of CFG
        self.require(SSA).perform_opt()

        # trick the DJ graph to use an empty CFG; this will serve
        # as our reachability graph, which will also track dominators
        self._reachable = ampy.types.CFG()
        self._reachable.create_block(self.CFG.entrypoint.label)
        self._reachable.set_entrypoint(self.CFG.entrypoint.label)
        self._DJ = DJGraph(self._reachable, [])

        # Step 1. RPO numbering
        # ---------------------
        # We need to rank blocks, instructions, and variables by their
        # RPO number. For the latter, this is necessary for tiebreaking
        # representatives for predicated identities (i.e. following a
        # brach conditional on A = B temporarily merges their value number
        # classes in the child block).
        #
        # rpo[i]: block with rpo number i
        # rpo_num[B]: the rpo number of a block
        # rpo_reg[v]: the rpo number of a register v
        # reg[i]: the register with rpo number i
        #
        # Step 2. Prepare VN tracking
        # ---------------------------
        # The value numbers will be represented by expressions in terms
        # of "RPO registers" (i.e., %n, where n is the RPO number of some
        # register). We need to track which instructions use certain
        # value number classes to flag them as needing updating if a
        # value number class changes.
        #
        # use[v]: set of (block, idx) pairs indicating instructions that
        #         use a given register to define another one
        # phivar[B, C]: list of pairs (i, var) stating that C[i] is a phi node
        #               which takes `var` from B
        # vn[expr]: value number for an expression
        self._rpo_num = {}
        self._rpo = []
        self._rpo_reg = {}
        self._reg = []

        self._use = {}
        self._phivar = {}
        self._vn = {}
        for block in reversed(self.CFG.postorder):
            self._rpo_num[block] = len(self._rpo)
            self._rpo.append(block)
            for i, I in enumerate(block):
                if isinstance(I, ampy.types.DefInstructionClass):
                    self._rpo_reg[I.target] = len(self._reg)
                    self._reg.append(I.target)

                # track uses
                match type(I):

                    case ampy.types.MovInstruction | ampy.types.WriteInstruction:
                        uses = [I.operand]
                    case ampy.types.PhiInstruction:
                        uses = []
                        for var, label in I.conds:
                            uses.append(var)
                            self._phivar.setdefault((self.CFG[label], block), []).append((i, var))
                    case ampy.types.BranchInstruction:
                        uses = [I.cond]
                    case T if issubclass(T, ampy.types.BinaryInstructionClass):
                        uses = I.operands
                    case _:
                        uses = []
                for use in filter(lambda s: s.startswith('%'), uses):
                    self._use.setdefault(use, set()).add((block, i))
        
        # Step 3. Touch and wipe until clean
        # ----------------------------------
        # Every instruction or block touched by a change is tracked, then they
        # get wiped in order of RPO number.
        #
        # Wiping a block amounts to updating necessary conditions for a block
        # to be reached. These conditions are likely not sufficient, as the true
        # conditions for reachability is a disjunction of statements, and we just
        # maintain a conjunction.
        #
        # Wiping an instruction amounts to updating value numbers for definitions
        # and propagating these changes to various uses (where the only relevant
        # uses are related to control flow, or other definitions). Expressions are
        # simplified using information provided by the predicates assumed of the
        # block.
        #
        # predicate[B]: conditions necessary for B to be reachable (partial predicate)
        # predicate[B, C]: conditions necessary for edge B -> C to be reachable
        # pred_supp[B[, C]]: local values used for computing the conditions above
        # pred_expr[B[, C]]: expression for the predicate, for update checking
        # phi[v][B]: assuming v is defined by a phi node, and B is one of the
        #            parent blocks, this gives a pair (state, cond), where
        #            `state` is the predicated state of coming via B, and
        #            `cond` is an expression summarising this state
        # phi_rep[phi]: representative target associated to `phi` (phi nodes
        #               are determined by all arguments except for the target).

        self._touched = []
        self._touchset = set()
        self._predicate = {}
        self._pred_supp = {}
        self._pred_expr = {}
        self._phi = {}
        self._phi_rep = {}

        self._touch(self.CFG.entrypoint)

        while len(self._touched) > 0:
            block, idx = self._pop_touch()
            if block not in self._reachable:
                # do not process unreachable blocks
                continue
            if idx == -1:
                # the block is touched, so update its predicate

                # get reachable parents from non-back-edges
                parents = list(filter(lambda p: self._rpo_num[p] <= self._rpo_num[block],
                            self._reachable[block.label].parents))
                if len(parents) == 0:
                    # block is entrypoint; no predication
                    self._predicate[block] = PredicatedState()
                    self._pred_supp[block] = set()
                elif len(parents) == 1:
                    # block is dominated by its parent
                    # inherit predicates from parent + condition to reach
                    # block from parent, if applicable
                    parent = list(parents)[0]
                    self.debug("Inheriting predicate from only parent", parent.label)
                    self._predicate[block] = self._predicate[parent, block]
                    self._pred_supp[block] = self._pred_supp[parent, block]
                else:
                    # block conditions are a disjunction of the conditions of
                    # its reachable parents; simplify by taking predicate of
                    # its immediate dominator, and no further conditions
                    idom = self._DJ.idom(block)
                    self.debug("Inheriting predicate from immediate dominator", idom.label)
                    self._predicate[block] = self._predicate[idom]
                    self._pred_supp[block] = self._pred_supp[idom]

                if ((expr := self._predicate[block].expr(self._pred_supp[block]))
                        != self._pred_expr.get(block, Expr(0))):
                    # predicate has changed; update predicate downstream
                    self.debug("Partial predicate of block", block.label, "has changed")
                    self._pred_expr[block] = expr
                    for i in range(len(block)):
                        self._touch(block, i)
                    for i in range(self._rpo_num[block]+1, len(self._rpo_num)):
                        self._touch(self._rpo[i], len(self._rpo[i])-1)
            else:
                # an instruction is touched
                I = block[idx]
                state = self._predicate[block]
                if isinstance(I, ampy.types.DefInstructionClass):
                    # touched definition, so recompute value number
                    self._update_value_number(I, state)
                elif isinstance(I, ampy.types.BranchInstructionClass):
                    # evaluate reachability for each child,
                    # store predicate, and observe changes in phi nodes
                    # if child is previously unreachable, touch all of its instructions
                    if isinstance(I, ampy.types.ExitInstruction):
                        # nothing to do
                        continue
                    if isinstance(I, ampy.types.GotoInstruction):
                        # unconditional branch
                        self._predicate[block, self.CFG[I.target]] = self._predicate[block]
                        self._pred_supp[block, self.CFG[I.target]] = set()
                    else:
                        # conditional branch
                        predicate = self._predicate[block]
                        cond = predicate.simplify(self._get_vn(I.cond))

                        iftrue = predicate.copy()
                        iftrue.assert_nonzero(cond)
                        if iftrue.consistent:
                            self._predicate[block, self.CFG[I.iftrue]] = iftrue
                            self._pred_supp[block, self.CFG[I.iftrue]] = self._cond_args(cond)

                        iffalse = predicate.copy()
                        iffalse.assert_zero(cond)
                        if iffalse.consistent:
                            self._predicate[block, self.CFG[I.iffalse]] = iffalse
                            self._pred_supp[block, self.CFG[I.iffalse]] = self._cond_args(cond)

                    for child in block.children:
                        if (block, child) not in self._predicate:
                            self.debug(child.label, "deemed unreachable from", block.label)
                            continue
                        
                        rblock = self._reachable[block.label] # dummy block
                        if child not in self._reachable:
                            # new reachable block
                            self.debug("Discovered new block", child.label)
                            self._reachable.create_block(child.label)
                            # touch newly reachable block
                            self._touch(child)
                            for i in range(len(child)):
                                self._touch(child, i)

                        rchild = self._reachable[child.label]
                        if rchild not in rblock.children:
                            if len(rblock.children) > 0:
                                rblock.add_child(rchild, cond="") # cond is unimportant in dummy
                            else:
                                rblock.add_child(rchild)

                            self._DJ.insert_edge(rblock, rchild)
                            self._touch(child)


                        # scan for phi nodes in child
                        dom = self._DJ.idom(child)
                        for idx, var in self._phivar.get((block, child), []):
                            predicate = self._predicate[block, child]
                            pred_expr = self._phi_pred(child, block, dom)
                            target = child[idx].target
                            if (block not in self._phi.setdefault(target, {})
                                    or pred_expr != self._phi[target][block][1]):
                                # touch changed phi node and update input
                                self.debug("Argument for phi node defining", target, "updated to", str(expr))
                                self._phi[target][block] = (predicate, pred_expr)
                                self._touch(child, idx)

        # Step 4. Eliminate unreachable blocks
        # ------------------------------------
        changed = False
        self.debug("Value numbering complete.")
        for block in list(filter(lambda block: block not in self._reachable, self.CFG)):
            self.debug(block.label, "is unreachable")
            changed = True
            self.CFG.remove_block(block.label)

        if changed:
            self.CFG.tidy()

        # Step 5. Record value numbers
        # ----------------------------
        vnclasses = {}
        for var, expr in self._vn.items():
            vnclasses.setdefault(self._unsub_rpo_nums(expr), set()).add(var.op)

        self.assign("classes")
        for expr, vnclass in vnclasses.items():
            self.assign("classes", expr.polish, append=True)
            self.assign("classes", *sorted(vnclass), append=True)
            self.assign("classes", '$', append=True)
        
        if changed:
            return tuple(filter(lambda opt: opt.ID in ("ssa", "gargi-gvn"), self.opts))
        return self.opts

    @GVN.getter
    @(Syntax(object) >> {str:Expr})
    def get_value_partitions(self):
        """
        Returns a mapping from variable names to "value numbers".
        The value number is always an Expr instance.
        """
        ret = {}
        expr = None
        i = 0
        cls_ls = self["classes"]
        while i < len(cls_ls):
            if cls_ls[i] == '$':
                expr = None
                i += 1
                continue
            if expr is None:
                expr, i = Expr.read_polish_ls(cls_ls, i)
                continue
            ret[cls_ls[i]] = expr
            i += 1

        return ret

    @(Syntax(object, Expr) >> Expr)
    def _unsub_rpo_nums(self, expr):
        """
        Rewrite the registers in an expression from those given by RPO
        numbers to the original register names
        """
        if isinstance(expr.op, int):
            return expr
        if isinstance(expr.op, str):
            num = int(expr.op[1:])
            return Expr(self._reg[num])
        return Expr(expr.op, *(self._unsub_rpo_nums(arg) for arg in expr.args))
    
    @classmethod
    @(Syntax(object, Expr) >> [set, Expr])
    def _cond_args(cls, cond):
        """
        Return the arguments of a condition, as per the logic of the
        predicate system
        """
        if isinstance(cond.op, (int, str)) or cond.op == ampy.types.PhiInstruction:
            return {cond}
        if issubclass(cond.op, ampy.types.CompInstructionClass):
            lhs, rhs = PredicatedState.split_subtraction(cond.right)
            return cls._cond_args(lhs) | cls._cond_args(rhs)
        
        return set(cond.args)

    @(Syntax(object, ampy.types.BasicBlock, ampy.types.BasicBlock, ampy.types.BasicBlock) >> Expr)
    def _phi_pred(self, child, block, dominator):
        """
        Construct the predicate for a phi node argument
        """
        self.debug(f"Computing phi predicate for the edge {block.label}->{child.label} (dominated by {dominator.label})")
        stack = []
        mem = {}
        stack.append((child, block))
        added = set()
        while len(stack) > 0:
            top = stack.pop()
            if top in mem:
                continue
            if isinstance(top, tuple):
                blk, pnt = top
                if pnt not in mem:
                    stack.append(top)
                    cur = pnt
                else:
                    cond = mem[pnt]
                    if len(self._reachable[pnt.label].children) > 1:
                        BI = self.CFG[pnt.label].branch_instruction
                        if cur.label == BI.iftrue:
                            # conjunction with branch condition
                            mem[blk, pnt] = Expr(ampy.types.AndInstruction, cond, self._get_vn(BI.cond))
                        else:
                            # conjunction with negation of branch condition
                            mem[blk, pnt] = Expr(ampy.types.AndInstruction, cond,
                                    Expr(ampy.types.XOrInstruction, Expr(-1), self._get_vn(BI.cond)))
                    else:
                        mem[blk, pnt] = cond
                    self.debug(f"Partial predicate for edge {pnt.label}->{blk.label} is {mem[blk, pnt]}")
            else:
                cur = top
            
            if cur == dominator:
                mem[cur] = Expr(-1)
                continue
            rcur = self._reachable[cur.label]
            parents = list(filter(lambda p: self._rpo_num[p] < self._rpo_num[cur], rcur.parents))
            doable = True
            for parent in parents:
                if (cur, parent) not in mem:
                    if doable:
                        doable = False
                        stack.append(cur)
                    if (cur, parent) not in added:
                        stack.append((cur, parent))
                        added.add((cur, parent))
                    break
            if not doable:
                continue
            
            mem[cur] = Expr(ampy.types.OrInstruction, *(mem[cur, parent] for parent in parents))
            self.debug(f"Partial predicate at block {cur.label} is {mem[cur]}")

        return mem[child, block]

    @(Syntax(object, ampy.types.BasicBlock)
      | Syntax(object, ampy.types.BasicBlock, int)
      >> None)
    def _touch(self, block, index=-1, /):
        rpo = self._rpo_num[block]
        if (rpo, index) in self._touchset:
            return
        if index == -1:
            self.debug("Touching", block.label)
        else:
            self.debug("Touching", block.label, "at instruction", index)
        self._touchset.add((rpo, index))
        heapq.heappush(self._touched, (rpo, index))

    @(Syntax(object) >> ((), ampy.types.BasicBlock, int))
    def _pop_touch(self):
        rpo, index = heapq.heappop(self._touched)
        self._touchset.remove((rpo, index))
        block = self._rpo[rpo]
        if index == -1:
            self.debug("Processing", block.label)
        else:
            self.debug("Processing", block.label, "at instruction", index)
        return self._rpo[rpo], index

    @(Syntax(object, str) >> Expr)
    def _get_vn(self, var):
        expr = Expr(var)
        if isinstance(expr.op, int):
            return expr
        return self._vn.get(expr, Expr('?'))

    @(Syntax(object, str) >> Expr)
    def _atomic_reg(self, var):
        """
        Returns the register rewritten as an RPO number
        """
        return Expr(f"%{self._rpo_reg[var]}")

    @(Syntax(object, ampy.types.DefInstructionClass, PredicatedState) >> None)
    def _update_value_number(self, I, state):
        """
        Using current information, update the value number of the variable defined
        by the instruction
        """
        if isinstance(I, ampy.types.BinaryInstructionClass):
            expr = Expr(type(I), *map(self._get_vn, I.operands))
            expr = state.simplify(expr)
        elif isinstance(I, ampy.types.MovInstruction):
            expr = self._get_vn(I.operand)
        elif isinstance(I, ampy.types.PhiInstruction):
            phiargs = []
            for var, label in I.conds:
                try:
                    state, cond = self._phi[I.target][self.CFG[label]]
                except KeyError:
                    # block has not yet been deemed "reachable"
                    continue
                phiargs.append((state.simplify(self._get_vn(var)), cond))
            phiargs = tuple(sorted(phiargs))
            if phiargs not in self._phi_rep:
                flat = []
                for var, cond in phiargs:
                    flat.append(var)
                    flat.append(cond)
                if Expr(I.target) in self._vn:
                    # pop old representative
                    oldphi = self._vn[Expr(I.target)]
                    if oldphi.op == ampy.types.PhiInstruction:
                        old = []
                        for i in range(len(oldphi.args)//2):
                            old.append((oldphi.args[2*i+1], oldphi.args[2*i+2]))
                        old = tuple(sorted(old))
                        if old in self._phi_rep:
                            del self._phi_rep[old]
                self._phi_rep[phiargs] = (
                        expr := Expr(type(I), self._atomic_reg(I.target), *flat))
            else:
                expr = self._phi_rep[phiargs]

        elif isinstance(I, ampy.types.ReadInstruction):
            # nothing we can do about reads
            expr = self._atomic_reg(I.target)

        if expr == (old := self._get_vn(I.target)):
            return

        self._vn[Expr(I.target)] = expr
        self.debug("Updating value number of", I.target, "from", str(old), "to", str(expr))

        # value of I.target changed, so all instructions using I.target
        # may need updating
        for block, idx in self._use.get(I.target, []):
            self._touch(block, idx)
