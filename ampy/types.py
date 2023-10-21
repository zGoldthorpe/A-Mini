import re

def _clean_whitespace(instr):
    """
    Cleans up instruction whitespace
    """
    return ' '.join(instr.strip().split())

class VarDict:
    """
    Data structure to store the value of virtual registers.
    Stores program counter as #pc (for branches)
    Also "stores" constants as themselves
    """

    def __init__(self, state={}):
        self._dict = {"#pc" : 0}
        self._phi = -1
        self.jumped = False # flag tracking if #pc was written to
        for key in state:
            self[key] = state[key]

    def __getitem__(self, key):
        if key in self._dict:
            return self._dict[key]
        # if not in dict, assume it's an integer
        return int(key)

    @property
    def vars(self):
        return sorted(tuple(self._dict.keys()))

    def is_var(self, key):
        return key in self._dict

    def __setitem__(self, key, value):
        if key not in self._dict:
            assert(key.startswith('%') or key.startswith('@'))

        assert(isinstance(value, int))
        self._dict[key] = value

    def __contains__(self, key):
        if key in self._dict:
            return True
        try:
            _ = int(key)
            return True
        except ValueError:
            return False

    def __iter__(self):
        for var in sorted(self._dict):
            yield var

    def compute_and_set(self, dest, *ops, func=lambda *x: sum(x)):
        """
        *ops is a list of arguments for VarDict
        func determines what to do with the arguments
        result is stored in dest
        returns nonzero value in case of error (undefined variable, etc.)
        """
        ops = list(ops)
        for (i, op) in enumerate(ops):
            if op not in self:
                return i+1
            ops[i] = self[op]

        rhs = func(*ops)
        if dest.startswith('%'):
            self[dest] = rhs
            return 0
        if dest == "#pc":
            self._phi = self["#pc"]
            self["#pc"] = rhs
            self.jumped = True
            return 0
        return -1 # destination is not a "register" or pc

    def phi_select(self, dest, *pairs):
        if not dest.startswith('%'):
            return -1
        for i, (op, label) in enumerate(pairs):
            if label not in self:
                return i+1
            if self[label] == self._phi:
                if op not in self:
                    return i+1
                self[dest] = self[op]
                return 0
        return -2

    def __repr__(self):
        lhs = "var"
        rhs = "val"
        maxllen = len(lhs)
        maxrlen = len(rhs)
        for key in self._dict:
            maxllen = max(maxllen, len(key))
            if key.startswith('%'):
                maxrlen = max(maxrlen, len(str(self._dict[key])))
            else:
                maxrlen = max(maxrlen, len(f"0x{self._dict[key]:04x}"))

        out = f"{lhs: >{maxllen}} | {rhs: >{maxrlen}}\n{'':->{maxllen}}-+-{'':->{maxrlen}}\n"
        for key in sorted(self._dict):
            if key.startswith('%'):
                out += f"{key: >{maxllen}} = {self._dict[key]: >{maxrlen}}\n"
            else:
                out += f"{key: >{maxllen}} = {f'0x{self._dict[key]:04x}': >{maxrlen}}\n"

        return out



class Operation:
    """
    Operation class for syntax parsing
    """
    def __init__(self, syntax_re, instr_cls):
        self.syntax = re.compile(syntax_re.replace(' ',r"\s*"))
        self.repr = syntax_re
        self.cls = instr_cls

    def __repr__(self):
        return f"Op({self.repr})"

    def read(self, instruction):
        m = self.syntax.fullmatch(_clean_whitespace(instruction))
        if m is None:
            return None
        return self.cls(*m.groups())

class InstructionClass:
    """
    Parent instruction type
    """
    def __init__(self, rep, typ, run=lambda var_dict:0):
        self._run = run
        self.type = typ
        self.repr = rep

    def __call__(self, var_dict):
        """
        Returns errno of instruction
        """
        return self._run(var_dict)

    def __repr__(self):
        return f"<{self.type}> {self.repr}"

# === General instruction classes ===

class ArithInstructionClass(InstructionClass):
    def __init__(self, rep, res, op1, op2, func):
        super().__init__(rep, "arith", lambda vd: vd.compute_and_set(res, op1, op2, func=func))
        self.target = res
        self.operands = (op1, op2)

class CompInstructionClass(InstructionClass):
    def __init__(self, rep, res, op1, op2, func):
        super().__init__(rep, "comp", lambda vd: vd.compute_and_set(res, op1, op2, func=func))
        self.target = res
        self.operands = (op1, op2)

class BranchInstructionClass(InstructionClass):
    def __init__(self, rep, *ops, func=lambda *x:0):
        super().__init__(rep, "branch", lambda vd: vd.compute_and_set("#pc", *ops, func=func))

# === Instruction types ===

class MovInstruction(InstructionClass):
    def __init__(self, lhs, rhs):
        super().__init__(f"{lhs} = {rhs}", "move", lambda vd: vd.compute_and_set(lhs, rhs, func=lambda x: x))
        self.target = lhs
        self.operand = rhs

class PhiInstruction(InstructionClass):
    def __init__(self, lhs, phi):
        conds = re.compile(rf"\[\s*{_op}\s*,\s*{_lbl}\s*\]")
        self.target = lhs
        self.phiops = []
        phirepr = f"{lhs} = phi"
        for cond in conds.finditer(phi):
            self.phiops.append((cond.group(1),cond.group(2)))
            phirepr += f" [ {cond.group(1)}, {cond.group(2)} ]"
        super().__init__(phirepr, "move", lambda vd: vd.phi_select(lhs, *self.phiops))


class AddInstruction(ArithInstructionClass):
    def __init__(self, dest, op1, op2):
        super().__init__(f"{dest} = {op1} + {op2}", dest, op1, op2, func=lambda x, y: x + y)

class SubInstruction(ArithInstructionClass):
    def __init__(self, dest, op1, op2):
        super().__init__(f"{dest} = {op1} - {op2}", dest, op1, op2, func=lambda x, y: x - y)

class MulInstruction(ArithInstructionClass):
    def __init__(self, dest, op1, op2):
        super().__init__(f"{dest} = {op1} * {op2}", dest, op1, op2, func=lambda x, y: x * y)

class EqInstruction(CompInstructionClass):
    def __init__(self, dest, op1, op2):
        super().__init__(f"{dest} = {op1} == {op2}", dest, op1, op2, func=lambda x, y: int(x == y))

class NeqInstruction(CompInstructionClass):
    def __init__(self, dest, op1, op2):
        super().__init__(f"{dest} = {op1} != {op2}", dest, op1, op2, func=lambda x, y: int(x != y))

class LtInstruction(CompInstructionClass):
    def __init__(self, dest, op1, op2):
        super().__init__(f"{dest} = {op1} < {op2}", dest, op1, op2, func=lambda x, y: int(x < y))

class LeqInstruction(CompInstructionClass):
    def __init__(self, dest, op1, op2):
        super().__init__(f"{dest} = {op1} <= {op2}", dest, op1, op2, func=lambda x, y: int(x <= y))

class GotoInstruction(BranchInstructionClass):
    def __init__(self, tgt):
        super().__init__(f"goto {tgt}", tgt, func=lambda x: x)
        self.target = tgt

class BranchInstruction(BranchInstructionClass):
    def __init__(self, cond, iftrue, iffalse):
        super().__init__(f"if ({cond}) goto {iftrue} else goto {iffalse}", cond, iftrue, iffalse, func=lambda x, y, z: y if x else z)
        self.cond = cond
        self.iftrue = iftrue
        self.iffalse = iffalse

def _safe_read():
    while True:
        try:
            return int(input())
        except ValueError:
            print("\033[31mPlease enter a valid integer.\033[m")

def _safe_write(value_dict, key):
    try:
        print(value_dict[key])
        return 0
    except KeyError:
        print("\033[31mundef\033[m")
        return -1

class ReadInstruction(InstructionClass):
    def __init__(self, lhs):
        super().__init__(f"read {lhs}", "I/O", lambda vd: vd.compute_and_set(lhs, func=_safe_read))

class WriteInstruction(InstructionClass):
    def __init__(self, lhs):
        super().__init__(f"write {lhs}", "I/O", lambda vd: _safe_write(vd, lhs))

def _dbgmsg(brk, var_dict):
    print(f"\033[32mBreakpoint {brk} reached.\n\033[33m{repr(var_dict)}",end='',flush=True)
    input("\033[32mPress <enter> to continue.\033[m")
    return 0

class BrkInstruction(InstructionClass):
    def __init__(self, name):
        super().__init__(f"{name} [breakpoint]", "debug", lambda vd: _dbgmsg(name, vd))

# operand regular expressions
_reg = r"%[.\w]+"
_var = rf"({_reg})"
_lbl = r"(@[.\w]+)"
_op = rf"({_reg}|-?\d+)"

opcodes = dict(
        # move
        mov = Operation(rf"{_var} = {_op}", MovInstruction),
        phi = Operation(rf"{_var} = phi ((?:\[ (?:%[.\w]+|-?\d+) , @[.\w]+ \],? )+)", PhiInstruction), # the regex is not exactly right, but it's fine
        # arithmetic
        add = Operation(rf"{_var} = {_op} \+ {_op}", AddInstruction),
        sub = Operation(rf"{_var} = {_op} - {_op}", SubInstruction),
        mul = Operation(rf"{_var} = {_op} \* {_op}", MulInstruction),
        # comparisons
        eq = Operation(rf"{_var} = {_op} == {_op}", EqInstruction),
        neq = Operation(rf"{_var} = {_op} != {_op}", NeqInstruction),
        lt = Operation(rf"{_var} = {_op} < {_op}", LtInstruction),
        leq = Operation(rf"{_var} = {_op} <= {_op}", LeqInstruction),
        # branching
        goto = Operation(rf"goto {_lbl}", GotoInstruction),
        branch = Operation(rf"branch {_op} \? {_lbl} : {_lbl}", BranchInstruction),
        # I/O
        read = Operation(rf"read {_var}", ReadInstruction),
        write = Operation(rf"write {_op}", WriteInstruction),
        # debugging
        brkpt = Operation(rf"brkpt !([.\w\d]+)", BrkInstruction)
    )
