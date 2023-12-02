"""
Simpson GVN algorithms
========================
Goldthorpe

Implements versions of GVN algorithms found in Simpson's PhD Thesis.

L.T. Simpson. 1996
    "Value-Driven Redundancy Elimination"
    PhD Thesis, Rice University
"""

from utils.syntax import Syntax

from opt.tools import Opt, OptError
from opt.ssa import SSA
from opt.gvn.expr import Expr

from ampy.passmanager import BadArgumentException
import ampy.types

class RPO(Opt):
    # forward declaration
    pass

class RPO(RPO):
    """
    Runs a GVN algorithm based on Simpson's RPO algorithm
    (Figure 4.3 of her PhD Thesis.)

    number: "var" or "expr"
        If "var", then value numbers are given by registers or constants.
        If "expr", then value numbers are given by expressions.
    """

    @RPO.init("gvn-rpo", "var")
    def __init__(self, number, /):
        if number not in ("var", "expr"):
            raise BadArgumentException("`number` must be one of \"var\" or \"expr\".")
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
                expr = vn.get(var, Expr('?'))
                return expr
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
                        args = [Expr(I.target)]
                        for val, label in I.conds:
                            arg = get_vn(val)
                            if arg.op == '?':
                                # be optimistic
                                continue
                            args.extend([arg, Expr(label)])
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

                    if ((self._number == "expr")
                            or isinstance(expr.op, (int, str))):
                        value = lookup.setdefault(expr, expr)
                    else:
                        value = lookup.setdefault(expr, Expr(I.target))

                    if value != get_vn(I.target):
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

        self.assign("classes")
        for val, vnclass in vnclasses.items():
            self.assign("classes", val.polish, append=True)
            self.assign("classes", *sorted(vnclass), append=True)
            self.assign("classes", '$', append=True)

        return self.opts

    @RPO.getter
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

class SCC(Opt):
    # forward declaration
    pass

class SCC(SCC):
    """
    Runs a GVN algorithm based on Simpson's SCC algorithm
    (Figure 4.7 of her PhD Thesis.)

    number: "var" or "expr"
        If "var", then value numbers are given by registers or constants.
        If "expr", then value numbers are given by expressions.
    """

    @SCC.init("gvn-scc", "var")
    def __init__(self, number, /):
        if number not in ("var", "expr"):
            raise BadArgumentException("`number` must be one of \"var\" or \"expr\".")
        self._number = number

    @SCC.opt_pass
    def gvn(self):
        # Step 1. Construct SSA graph
        # ---------------------------
        # If the code is in SSA form, the SSA graph is a labelled graph where
        # nodes correspond to constants or operations, and edges connect
        # nodes to their arguments (with an order).
        # Nodes are labelled by the variable they define.
        #
        # We track the order of node visit in reversed postorder for later
        #
        # rpo: list of variables visited in reversed postorder
        # idx[var]: index of var in rpo
        # ssa[var]: (op/const, [tuple of operands])
        self.require(SSA).perform_opt()
        
        self._ssa = {}
        rpo = []
        idx = {}
        for block in reversed(self.CFG.postorder):
            for i, I in enumerate(block):
                if not isinstance(I, ampy.types.DefInstructionClass):
                    continue
                idx[I.target] = len(rpo)
                rpo.append(I.target)
                if isinstance(I, ampy.types.BinaryInstructionClass):
                    self._ssa[I.target] = (type(I), I.operands)
                elif isinstance(I, ampy.types.PhiInstruction):
                    self._ssa[I.target] = (type(I),
                            tuple(tuple(pair) for pair in I.conds))
                elif isinstance(I, ampy.types.MovInstruction):
                    self._ssa[I.target] = (type(I), (I.operand,))
                else:
                    # read instruction, or perhaps an instruction type that
                    # was introduced after this algorithm was made
                    self._ssa[I.target] = (type(I), ())

        # Step 2. Find SCC
        # ----------------
        # Simpson observed that the RPO GVN algorithm only has nontrivial
        # work in strongly connected components of the SSA graph.
        #
        # Step 3. Run RPO on SCCs
        # -----------------------
        # This is combined with step 2, so as to process SCCs the moment
        # they are built.
        # The value numbering for a variable is optimistic at first (i.e.
        # could be false), so is not stored as valid until it is finished
        # being processed.
        #
        # vn[var]: valid value number of variable
        # valid[expr]: validated value number of an expression
        # optimistic[expr]: optimistic value number of an expression
        self._vn = {}
        self._valid = {}
        self._optimistic = {}

        # Tarjan algorithm data
        tarjannum = {}
        tarjanlow = {}
        stack = []
        stackset = set()
        def tarjan(var):
            """
            Tarjan DFS for finding SCCs
            """
            tarjannum[var] = len(tarjannum)
            tarjanlow[var] = tarjannum[var]
            if var not in self._ssa:
                # only possible if var is a constant
                return
            stack.append(var)
            stackset.add(var)
            for child in self._ssa[var][1]:
                if isinstance(child, tuple):
                    child = child[0]
                if child not in tarjannum:
                    tarjan(child)
                    tarjanlow[var] = min(tarjanlow[var], tarjanlow[child])
                if tarjannum[child] < tarjannum[var] and child in stackset:
                    tarjanlow[var] = min(tarjanlow[var], tarjannum[child])
            if tarjanlow[var] == tarjannum[var]:
                # new SCC
                scc = []
                while True:
                    node = stack.pop()
                    stackset.remove(node)
                    scc.append(node)
                    if node == var:
                        break
                self.debug("Processing SSA SCC:", scc)
                self._process_scc(sorted(scc, key=lambda v: idx[v]))

        for var in rpo:
            if var not in tarjannum:
                tarjan(var)

        # Step 3. Record  value number classes
        # ------------------------------------
        self.debug("Value numbering complete")
        vnclasses = {}
        for var, val in self._vn.items():
            vnclasses.setdefault(val, set()).add(var)

        self.assign("classes")
        for val, vnclass in vnclasses.items():
            self.assign("classes", val.polish, append=True)
            self.assign("classes", *sorted(vnclass), append=True)
            self.assign("classes", '$', append=True)

        return self.opts

    @SCC.getter
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

    @(Syntax(object, [list, str]) >> None)
    def _process_scc(self, scc):
        """
        Compute the value numbers for a SCC of SSA graph
        """
        if len(scc) == 1:
            var = scc[0]
            self._get_number(var, self._valid)
            return
        changed = True
        while changed:
            changed = False
            self.debug("Updating SCC value numbers")
            for var in scc:
                # optimistically number the variables
                # until a fixed point is reached
                changed |= self._get_number(var, self._optimistic)
        for var in scc:
            # commit the value numbering
            self._get_number(var, self._valid)

    def _get_number(self, var, lookup):
        """
        Valuate variable based on lookup table.
        """
        def get_vn(var):
            if var.startswith('%'):
                expr = self._vn.get(var, Expr('?'))
                return expr
            return Expr(int(var))
        
        op, args = self._ssa[var]
        match op:
            case ampy.types.MovInstruction:
                expr = get_vn(args[0])
            case ampy.types.PhiInstruction:
                phiargs = [Expr(var)]
                for val, label in args:
                    vn = get_vn(val)
                    if vn.op == '?': # optimistically discard unknown values
                        continue
                    phiargs.extend([vn, Expr(label)])
                expr = Expr(op, *phiargs)
            case T if issubclass(T, ampy.types.BinaryInstructionClass):
                op1, op2 = map(get_vn, args)
                expr = Expr(T, op1, op2)
            case _:
                # if var is a constant, then this gives the constant
                # otherwise, it is an unhandled definition class, or a read
                # cannot be optimistic in those cases
                expr = Expr(var)

        if (self._number == "expr" or isinstance(expr.op, (int, str))):
            # do not expand phi instructions as expressions
            # or else you will face infinite loops
            value = lookup.setdefault(expr, expr)
        else:
            value = lookup.setdefault(expr, Expr(var))

        if var not in self._vn or value != self._vn[var]:
            self._vn[var] = value
            self.debug(f"{var} updated to {value}")
            return True

        return False
