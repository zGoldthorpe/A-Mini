"""
Abstract expressions
======================
Goldthorpe

This module provides a datatype for managing abstract computation expressions,
primarily for value numbering.
"""

from utils.syntax import Syntax, Assertion
from opt.tools import OptError

import ampy.types as amt

class Expr:
    # forward declaration

    # constant declaring the number of bits used for ints
    intsize = 128

class Expr(Expr):
    """
    Formal computational expression, with rewriting rules
    """
    @(Syntax(object, int, reduce=bool)
      | Syntax(object, str, reduce=bool)
      | Syntax(object, ((type, Assertion(lambda T: issubclass(T, amt.DefInstructionClass))),), Expr, ..., reduce=bool))
    def __init__(self, op, *exprs, reduce=True):
        # an expression is an AST whose leaf nodes are constants / registers
        #
        # op: operation or constant
        # args: arguments
        if isinstance(op, str):
            try:
                op = self._int(int(op))
            except ValueError:
                pass
        self.op = op
        self.args = list(exprs)
        if reduce:
            self.reduce()

    ### convenient getters/setters ###

    @property
    @(Syntax(object) >> Expr)
    def left(self):
        return self.args[0]
    @left.setter
    @(Syntax(object, Expr) >> None)
    def left(self, expr):
        self.args[0] = expr

    @property
    @(Syntax(object) >> Expr)
    def right(self):
        return self.args[-1]
    @right.setter
    @(Syntax(object, Expr) >> None)
    def right(self, expr):
        self.args[-1] = expr

    @property
    @(Syntax(object) >> [iter, Expr])
    def subexpressions(self):
        """
        Yields subepressions in bottom-up order
        """
        outs = set()
        def collect(node, depth):
            outs.add((node, depth))
            for arg in node.args:
                collect(arg, depth+1)
        collect(self, 0)
        for node, _ in sorted(outs, key=lambda p: -p[1]):
            yield node

    ### for printing ###
    
    def __str__(self):

        if isinstance(self.op, (int, str)):
            rep = str(self.op)
            if rep.startswith('-'):
                return f"({rep})"
            return rep

        if issubclass(self.op, amt.BinaryInstructionClass):
            return "({})".format(f" {self.op.op} ".join(str(arg) for arg in self.args))

        if self.op == amt.PhiInstruction:
            phiargs = "; ".join("{}, {}".format(str(self.args[2*i+1]), str(self.args[2*i+2]))
                            for i in range(len(self.args)//2))
            return f"phi[{self.args[0].op}]({phiargs})"

        # new definition instruction
        return f"{self.op}({', '.join(str(arg) for arg in self.args)})"

    def __repr__(self):
        return f"Expr<{self}>"

    ### for emitting A-Mi instructions ###

    @property
    @(Syntax(object) >> tuple)
    def recipe(self):
        """
        Emit the last instruction for a construction of this
        expression in the form (op, *args)
        """
        if isinstance(self.op, (int, str)):
            return (str(self.op),)

        if self.op == amt.PhiInstruction:
            # phi recipe is (Phi, (target, *conds))
            # where conds are expr-str pairs
            phiargs = []
            for i in range(len(self.args)//2):
                if isinstance(self.args[2*i+2].op, str):
                    phiargs.append((self.args[2*i+1], self.args[2*i+2].op))
                else:
                    for labelexpr in self.args[2*i+2].args:
                        phiargs.append((self.args[2*i+1], labelexpr.op))
            return (self.op, (self.args[0].op, phiargs))

        # undo some canonicalisations
        if self.op == amt.AddInstruction:
            # a - b = a + (-1)b
            sums = []
            subs = []
            for arg in self.args:
                if (arg.op == amt.MulInstruction
                        and isinstance(arg.left.op, int)
                        and arg.left.op < 0):
                    subs.append(Expr(amt.MulInstruction,
                                    Expr(-arg.left.op),
                                    arg.right))
                elif isinstance(arg.op, int) and arg.op < 0:
                    subs.append(Expr(-arg.op))
                else:
                    sums.append(arg)
            if len(subs) > 0:
                return (amt.SubInstruction,
                            (Expr(amt.AddInstruction, *sums),
                             Expr(amt.AddInstruction, *subs)))
        if issubclass(self.op, amt.CompInstructionClass):
            # (a == b) = (0 == a - b) etc.
            right = self.right.recipe
            if right[0] == amt.SubInstruction:
                return (self.op, (right[1][1], right[1][0]))

        if len(self.args) > 2:
            tail = Expr(self.op, *self.args[1:])
            return (self.op, (self.left, tail))

        # other canonicalisations
        if (self.op == amt.MulInstruction
                and isinstance(self.left.op, int)):
            if self.left.op > 0:
                b = bin(self.left.op)
                if b.count('1') == 1:
                    # (2**n * a) = (a << n)
                    return (amt.LShiftInstruction,
                                (self.right,
                                    Expr(len(b)-3))) # len(bin(2**n)) = n+3

        return (self.op, (self.left, self.right))
            

    ### for metadata ###

    @property
    @(Syntax(object) >> str)
    def polish(self):
        """
        Convert expression into Polish notation.
        All operations come with a specified arity as "op`arity"
        """
        if isinstance(self.op, (int, str)):
            return f"{self.op}"
        if issubclass(self.op, amt.BinaryInstructionClass):
            op = self.op.op
        elif self.op == amt.PhiInstruction:
            op = "phi"
        else: # should not be possible
            op = "?"
        return f"{op}`{len(self.args)} " + ' '.join(arg.polish for arg in self.args)

    @classmethod
    @(Syntax(object, str) >> Expr)
    def read_polish(cls, polish):
        """
        Parse Polish notation
        """
        return cls.read_polish_ls(polish.split(), 0)[0]

    @classmethod
    @(Syntax(object, [str], int) >> ((), Expr, int))
    def read_polish_ls(cls, polish, i):
        """
        Given the Polish expr as a list of terms, and a starting index i,
        returns a pair (expr, j), where expr is the expression obtained by
        parsing the terms in the interval [i, j).
        """
        if '`' not in polish[i]:
            return Expr(polish[i]), i+1

        op, arity = polish[i].split('`', 1)
        arity = int(arity)

        # collect all arguments
        args = []
        j = i+1
        for _ in range(arity):
            expr, j = Expr.read_polish_ls(polish, j)
            args.append(expr)

        match op:
            case '+':
                return Expr(amt.AddInstruction, *args), j
            case '-':
                return Expr(amt.SubInstruction, *args), j
            case '*':
                return Expr(amt.MulInstruction, *args), j
            case '/':
                return Expr(amt.DivInstruction, *args), j
            case '%':
                return Expr(amt.ModInstruction, *args), j
            case '&':
                return Expr(amt.AndInstruction, *args), j
            case '|':
                return Expr(amt.OrInstruction, *args), j
            case '^':
                return Expr(amt.XOrInstruction, *args), j
            case "<<":
                return Expr(amt.LShiftInstruction, *args), j
            case ">>":
                return Expr(amt.RShiftInstruction, *args), j
            case "==":
                return Expr(amt.EqInstruction, *args), j
            case "!=":
                return Expr(amt.NeqInstruction, *args), j
            case '<':
                return Expr(amt.LtInstruction, *args), j
            case "<=":
                return Expr(amt.LeqInstruction, *args), j
            case "phi":
                return Expr(amt.PhiInstruction, *args), j
            case T:
                # shouldn't happen
                raise NotImplementedError(f"Unrecognised operand {T} of arity {arity}.")


    ### comparisons ###
    @(Syntax(object, Expr) >> int)
    def compare(self, other):
        """
        Returns -1, 0, 1 if self is lt, eq, gt other (respectively).
        Total ordering is somewhat arbitrary:
        integers < registers
        expressions with matching operations are sorted by arity
        then sorted in lexicographical order by arguments
        """
        def cmp(a, b):
            return (a > b) - (a < b)
        if self.op == other.op:
            if isinstance(self.op, (int, str)):
                return 0
            if (res := cmp(len(self.args), len(other.args))) != 0:
                return res
            mulligan = self.op == amt.PhiInstruction
            # phi instructions should be identified even if their target
            # registers are different (since that is just for avoiding
            # nesting)
            for L, R in zip(self.args, other.args):
                if mulligan:
                    mulligan = False
                    continue
                if (res := L.compare(R)) != 0:
                    return res
            return 0

        if isinstance(self.op, int):
            if isinstance(other.op, int):
                return cmp(self.op, other.op)
            return -1
        if isinstance(other.op, int):
            return +1
        if isinstance(self.op, str):
            if isinstance(other.op, str):
                return cmp(self.op, other.op)
            return -1
        if isinstance(other.op, str):
            return +1

        order = (
                amt.AddInstruction,
                amt.SubInstruction,
                amt.MulInstruction,
                amt.AndInstruction,
                amt.OrInstruction,
                amt.XOrInstruction,
                amt.EqInstruction,
                amt.NeqInstruction,
                amt.LtInstruction,
                amt.LeqInstruction,
                amt.LShiftInstruction,
                amt.RShiftInstruction,
                amt.DivInstruction,
                amt.ModInstruction,
                amt.PhiInstruction,
                )

        for op in order:
            if self.op == op:
                return -1
            if other.op == op:
                return +1

        # we should not be able to reach here
        raise NotImplementedError

    @(Syntax(object, Expr) >> bool)
    def __eq__(self, other):
        return self.compare(other) == 0

    @(Syntax(object, Expr) >> bool)
    def __ne__(self, other):
        return self.compare(other) != 0

    @(Syntax(object, Expr) >> bool)
    def __lt__(self, other):
        return self.compare(other) == -1

    @(Syntax(object, Expr) >> bool)
    def __le__(self, other):
        return self.compare(other) <= 0

    def __hash__(self):
        #TODO: don't hash; this data structure is inefficient to
        # hash and then check equality with
        if self.op == amt.PhiInstruction:
            return hash((self.op, tuple(self.args[1:])))
        return hash((self.op, tuple(self.args)))
    
    @classmethod
    @(Syntax(object, int) >> int)
    def _int(cls, x):
        """
        Ensure integer is within the specified bit range
        """
        if cls.intsize > 0:
            x = x % (1 << cls.intsize)
            if x > 1 << (cls.intsize-1):
                x -= 1 << cls.intsize
        return x

    ### rewriting ###
    @(Syntax(object) >> None)
    def reduce(self):
        """
        Apply rewriting rules to put expression into a canonical form.
        The hope is that two expressions are equivalent precisely if
        their canonical forms coincide, but this will only be an approximation
        since I am not thinking through all possible rewriting rules.

        The assumption is that the operands are already reduced.
        """
        # rewriting rules implemented:
        # redundancy: a - b = a + (-1)*b
        # associativity: +, *, &, |, ^
        # commutativity: +, *, &, |, ^
        # c-distributivity: (*,+) (&,|^)
        #    (we do not distribute (|,&) as this would cause infinite recursion)
        # l-distrivutivity: (<<,+&|^), (>>,&|^)
        # exponent rules for << and >>

        if isinstance(self.op, (int, str)):
            return

        # nested phi nodes are prohibited
        for i, arg in list(enumerate(self.args)):
            if arg.op == amt.PhiInstruction:
                self.args[i] = arg.args[0]

        while True:

            match self.op:

                case amt.PhiInstruction:
                    # not much we can do with these
                    # besides group its operands by label and hope things align
                    #
                    # NB: nested phi instructions are prohibited
                    # phi arguments are stored as:
                    # (target, var1, lbl1, var2, lbl2, ...)
                    #TODO: uses hashing
                    mapping = {}
                    for i in range(len(self.args)//2):
                        val = self.args[2*i+1]
                        label = self.args[2*i+2]
                        mapping.setdefault(val, set()).add(label)
                    if len(mapping) == 1:
                        # phi is actually just a copy
                        new, _ = mapping.popitem()
                        self.op = new.op
                        self.args = new.args
                        return
                    self.args = [self.args[0]]
                    for val, labelset in sorted(mapping.items()):
                        self.args.append(val)
                        self.args.append(Expr(amt.OrInstruction, *labelset))
                    return

                case amt.AddInstruction:
                    self._assoc()
                    # now, group like terms, where terms are summands
                    # except a constant multiplication coefficient
                    #TODO: this uses hashing
                    terms = {}
                    for arg in self.args:
                        if arg.op == 0:
                            continue
                        if isinstance(arg.op, int):
                            terms[Expr(1)] = terms.get(Expr(1), 0) + arg.op
                        elif (arg.op == amt.MulInstruction
                                and isinstance(arg.left.op, int)):
                            if len(arg.args) > 2:
                                e = Expr(amt.MulInstruction, *arg.args[1:], reduce=False)
                            else:
                                e = arg.right
                            terms[e] = terms.get(e, 0) + arg.left.op
                        else:
                            terms[arg] = terms.get(arg, 0) + 1

                    self.args = sorted(Expr(amt.MulInstruction, Expr(coef), term)
                            for term, coef in terms.items() if coef != 0)
                    
                    if len(self.args) == 0:
                        self.op = 0
                        break
                    if len(self.args) == 1:
                        self.op = self.left.op
                        self.args = self.left.args
                        break

                case amt.SubInstruction:
                    # a - b = a + (-1)*b
                    self.op = amt.AddInstruction
                    self.right = Expr(amt.MulInstruction, Expr(-1), self.right)
                    continue

                case amt.MulInstruction:
                    self._assoc()
                    if self._distribute(amt.AddInstruction):
                        continue
                    # use commutativity to reorganise factors and group consts
                    const = 1
                    kept = []
                    for arg in self.args:
                        if isinstance(arg.op, int):
                            const *= arg.op
                            if const == 0:
                                break
                        else:
                            kept.append(arg)
                    if const == 0 or len(kept) == 0:
                        self.op = const
                        self.args = []
                        break
                    if const != 1:
                        kept.append(Expr(const))
                    self.args = sorted(kept)

                    if len(self.args) == 1:
                        self.op = self.left.op
                        self.args = self.left.args

                case amt.DivInstruction:
                    if self.right.op == 0:
                        # division by zero!
                        #TODO: can we do something about this
                        # (maybe an "undef" expression value)
                        # for now, treat as zero
                        self.op = 0
                        self.args = []
                        break
                    if self.right.op == 1:
                        # a / 1 = a
                        self.op = self.left.op
                        self.args = self.left.args
                        break
                    if self.left.op == 0:
                        # 0 / a = 0
                        self.op = 0
                        self.args = []
                        break
                    if self.right.op == -1:
                        # a / (-1) = (-1) * a
                        self.op = amt.MulInstruction
                        self.right = self.left
                        self.left = Expr(-1)
                        continue
                    if self.left == self.right:
                        # a / a = 1
                        self.op = 1
                        self.args = []
                        break
                    if isinstance(self.left.op, int) and isinstance(self.right.op, int):
                        self.op = self.left.op // self.right.op
                        self.args = []
                        break

                case amt.ModInstruction:
                    if self.right.op == 0:
                        # modulo zero!
                        #TODO: can we do something about this
                        # for now, treat as zero
                        self.op = 0
                        self.args = []
                        break
                    if (self.left.op == 0
                            or (isinstance(self.right.op, int)
                                and abs(self.right.op) == 1)
                            or self.left == self.right):
                        # 0 % b = 0
                        # a % 1 = a % (-1) = 0
                        # a % a = 0
                        self.op = 0
                        self.args = []
                        break
                    if isinstance(self.left.op, int) and isinstance(self.right.op, int):
                        self.op = self.left.op % self.right.op
                        self.args = []
                        break

                case amt.AndInstruction:
                    self._assoc()
                    if self._distribute(amt.OrInstruction, amt.XOrInstruction):
                        continue

                    # use commutativity to collapse dupes and reduce consts
                    #TODO: uses hashing
                    const = -1
                    argset = set()
                    for arg in self.args:
                        if isinstance(arg.op, int):
                            const &= arg.op
                            if const == 0:
                                break
                        else:
                            argset.add(arg)
                    if const == 0 or len(argset) == 0:
                        # and with zero is zero
                        self.op = const
                        self.args = []
                        break
                    if const != -1:
                        argset.add(Expr(const))
                    self.args = sorted(argset)

                    if len(self.args) == 1:
                        self.op = self.left.op
                        self.args = self.left.args
                        break

                case amt.OrInstruction:
                    self._assoc()

                    # use commutativity to collapse dupes and reduce consts
                    const = 0
                    argset = set()
                    for arg in self.args:
                        if isinstance(arg.op, int):
                            const |= arg.op
                            if const == -1:
                                break
                        else:
                            argset.add(arg)
                    if const == -1 or len(argset) == 0:
                        # or with -1 is -1
                        self.op = const
                        self.args = []
                        break
                    if const != 0:
                        argset.add(Expr(const))
                    self.args = sorted(argset)

                    #TODO: absorption? a | (a & b) = a

                    if len(self.args) == 1:
                        self.op = self.left.op
                        self.args = self.left.args

                case amt.XOrInstruction:
                    self._assoc()

                    # use commutativity to cancel dupes and reduce consts
                    const = 0
                    argset = set()
                    for arg in self.args:
                        if isinstance(arg.op, int):
                            const ^= arg.op
                        else:
                            try:
                                argset.remove(arg)
                            except KeyError:
                                argset.add(arg)
                    if len(argset) == 0:
                        self.op = const
                        self.args = []
                        break
                    if const != 0:
                        argset.add(Expr(const))

                    self.args = sorted(argset)

                    if len(self.args) == 1:
                        self.op = self.left.op
                        self.args = self.left.args

                case amt.LShiftInstruction:
                    if self._distribute_left(
                            amt.AddInstruction,
                            amt.AndInstruction,
                            amt.OrInstruction,
                            amt.XOrInstruction):
                        continue
                    
                    # exponent rules
                    if self.left.op == amt.LShiftInstruction:
                        # (a << b) << c = a << (b + c)
                        self.right = Expr(
                                amt.AddInstruction,
                                self.left.right,
                                self.right)
                        self.left = self.left.left
                        continue
                    if self.left.op == amt.RShiftInstruction:
                        # (a >> b) << b = a
                        if self.left.right == self.right:
                            self.op = self.left.left.op
                            self.args = self.left.left.args
                            break

                    if self.left.op == 0:
                        # 0 << a = 0
                        self.op = 0
                        self.args = []
                        break

                    if isinstance(self.right.op, int):
                        if isinstance(self.left.op, int):
                            if self.right.op >= 0:
                                self.op = self.left.op << self.right.op
                            else:
                                self.op = self.left.op >> -self.right.op
                            self.args = []
                            break
                        if (n := self.right.op) >= 0:
                            # a << n = (2**n) * a
                            self.op = amt.MulInstruction
                            self.right = self.left
                            self.left = Expr(2**n)
                            continue
                        # a << (-n) = a >> n
                        self.right = Expr(-self.right.op)
                        self.op = amt.RShiftInstruction

                case amt.RShiftInstruction:
                    if self._distribute_left(
                            amt.AndInstruction,
                            amt.OrInstruction,
                            amt.XOrInstruction):
                        continue

                    # exponent rules
                    if self.left.op == amt.LShiftInstruction:
                        # (a << b) >> c = a << (b - c)
                        self.right = Expr(
                                amt.SubInstruction,
                                self.left.right,
                                self.right)
                        self.left = self.left.left
                        self.op = amt.LShiftInstruction
                        continue
                    if self.left.op == amt.RShiftInstruction:
                        # (a >> b) >> c = a >> (b + c)
                        self.right = Expr(
                                amt.AddInstruction,
                                self.left.right,
                                self.right)
                        self.left = self.left.left
                        continue

                    if self.left.op == 0:
                        # 0 >> n = 0
                        self.op = 0
                        self.args = []
                        break

                    if isinstance(self.right.op, int):
                        if isinstance(self.left.op, int):
                            if self.right.op >= 0:
                                self.op = self.left.op >> self.right.op
                            else:
                                self.op = self.left.op << -self.right.op
                            self.args = []
                            break
                        if self.right.op <= 0:
                            # a >> (-n) = a << n
                            self.op = amt.LShiftInstruction
                            self.right = Expr(-self.right.op)
                            continue

                case amt.EqInstruction:
                    if self.left == self.right:
                        self.op = 1
                        self.args = []
                        break
                    if isinstance(self.left.op, int) and isinstance(self.right.op, int):
                        self.op = 0
                        self.args = []
                        break
                    if self.left.op != 0:
                        self.right = Expr(amt.SubInstruction, self.right, self.left)
                        self.left = Expr(0)
                        continue

                case amt.NeqInstruction:
                    if self.left == self.right:
                        self.op = 0
                        self.args = []
                        break
                    if isinstance(self.left.op, int) and isinstance(self.right.op, int):
                        self.op = 1
                        self.args = []
                        break
                    if self.left.op != 0:
                        self.right = Expr(amt.SubInstruction, self.right, self.left)
                        self.left = Expr(0)
                        continue

                case amt.LtInstruction:
                    if self.left == self.right:
                        self.op = 0
                        self.args = []
                        break
                    if isinstance(self.left.op, int) and isinstance(self.right.op, int):
                        self.op = int(self.left.op < self.right.op)
                        self.args = []
                        break
                    if self.left.op != 0:
                        self.right = Expr(amt.SubInstruction, self.right, self.left)
                        self.left = Expr(0)
                        continue

                case amt.LeqInstruction:
                    if self.left == self.right:
                        self.op = 1
                        self.args = []
                        break
                    if isinstance(self.left.op, int) and isinstance(self.right.op, int):
                        self.op = int(self.left.op <= self.right.op)
                        self.args = []
                        break
                    if self.left.op != 0:
                        self.right = Expr(amt.SubInstruction, self.right, self.left)
                        self.left = Expr(0)
                        continue

                case _:
                    # shouldn't happen
                    pass

            # after all the reductions happen, exit the loop
            break

        if isinstance(self.op, int):
            # cap the bitsize of integers
            self.op = self._int(self.op)
    

    ## associativity ##
    @(Syntax(object) >> None)
    def _assoc(self):
        """
        Assuming expression is associative, regroups expression as
        a . (b . c) = a . b . c
        (a . b) . c = a . b . c
        """
        newargs = []
        for arg in self.args:
            if arg.op == self.op:
                newargs.extend(arg.args)
            else:
                newargs.append(arg)
        self.args = newargs
    
    ## distributivity ##
    @(Syntax(object, type, ...) >> bool)
    def _distribute(self, *ops):
        """
        Distributes self.op over the ops specified, and return True
        if distribution occurs
        """
        for i, arg in enumerate(self.args):
            op = self.op
            if arg.op in ops:
                # a . (b : c) . d = (a . b . d) : (a . c . d)
                self.op = arg.op
                self.args = [Expr(op, *self.args[:i], aa, *self.args[i+1:])
                        for aa in arg.args]
                return True
        return False

    @(Syntax(object, type, ...) >> bool)
    def _distribute_left(self, *ops):
        """
        Distributes (a : b) . c = (a . c) : (b . c)
        """
        if self.left.op in ops:
            op = self.op
            self.op = self.left.op
            self.args = [Expr(op, arg, self.right) for arg in self.left.args]
            return True
        return False
