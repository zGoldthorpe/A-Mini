from ampy.ensuretypes import Syntax, ensure_types, ensure_multi

### Instructions ###

class InstructionClass:
    """
    Parent instruction type
    """
    def __init__(self, rep, typ):
        self.type = typ
        self.repr = rep

    def __repr__(self):
        return f"<{self.type}> {self.repr}"

### General instruction classes ###

class ArithInstructionClass(InstructionClass):
    def __init__(self, rep, res, op1, op2, func):
        super().__init__(rep, "arith")
        self.target = res
        self.operands = (op1, op2)

class CompInstructionClass(InstructionClass):
    def __init__(self, rep, res, op1, op2, func):
        super().__init__(rep, "comp")
        self.target = res
        self.operands = (op1, op2)

class BranchInstructionClass(InstructionClass):
    def __init__(self, rep):
        super().__init__(rep, "branch")

### Instruction types ###

class MovInstruction(InstructionClass):
    def __init__(self, lhs, rhs):
        super().__init__(f"{lhs} = {rhs}", "move")
        self.target = lhs
        self.operand = rhs

class PhiInstruction(InstructionClass):
    def __init__(self, lhs, phiargs):
        conds = re.compile(rf"\[\s*{_op}\s*,\s*{_lbl}\s*\]")
        self.target = lhs
        self.phiops = []
        phirepr = f"{lhs} = phi"
        for cond in conds.finditer(phiargs):
            self.phiops.append((cond.group(1),cond.group(2)))
            phirepr += f" [ {cond.group(1)}, {cond.group(2)} ]"
        super().__init__(phirepr, "move")

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
    def __init__(self, tgt:str):
        super().__init__(f"goto {tgt}")
        self.target = tgt

class BranchInstruction(BranchInstructionClass):
    def __init__(self, cond:str, iftrue:str, iffalse:str):
        super().__init__(f"if ({cond}) goto {iftrue} else goto {iffalse}")
        self.cond = cond
        self.iftrue = iftrue
        self.iffalse = iffalse

class ReadInstruction(InstructionClass):
    def __init__(self, lhs):
        super().__init__(f"read {lhs}", "I/O")
        self.target = lhs

class WriteInstruction(InstructionClass):
    def __init__(self, lhs):
        super().__init__(f"write {lhs}", "I/O")
        self.target = lhs

class BrkInstruction(InstructionClass):
    def __init__(self, name):
        super().__init__(f"{name} [breakpoint]", "debug", lambda vd: _dbgmsg(name, vd))
        self.id = name

### Basic blocks ###
class BasicBlock:
    class _BranchTargets:
        pass

class BasicBlock(BasicBlock):
    class _BranchTargets(BasicBlock._BranchTargets):
        @ensure_multi(
                Syntax(BasicBlock._BranchTargets), # exit node; no children
                Syntax(BasicBlock._BranchTargets, target=BasicBlock), # goto
                Syntax(BasicBlock._BranchTargets, cond=BasicBlock, iftrue=BasicBlock, iffalse=BasicBlock), # branch
                )
        def __init__(self, target=None, cond=None, iftrue=None, iffalse=None):
            self._target = target
            self._cond = cond
            self._iftrue = iftrue
            self._iffalse = iffalse

        def __eq__(self, other:BasicBlock._BranchTargets):
            return (self._target == other._target
                    and self._cond == other.cond
                    and self._iftrue == other._iftrue
                    and self._iffalse == other.iffalse)

        @property
        def children(self):
            if self._cond is not None:
                return (self._iftrue, self._iffalse)
            if self._target is not None:
                return (self._target,)
            return ()

        @property
        def branch_condition(self):
            return self._cond

class BasicBlock(BasicBlock):

    def __init__(self, label:str, instructions:list=[], branch_targets=BasicBlock._BranchTargets(), parents=set()):
        """
        label: string @label indicating block's "name"
        instructions: list of Instruction objects
        parents: set of BasicBlock objects pointing to parents
        """
        self._label = label
        self._instructions = list(instructions)
        self._branch_targets = branch_targets
        self._parents = set(parents)

    def __repr__(self):
        return (f"{self.name}\n{'':->{len(self.name)}}\n"
                + "parents: " + ", ".join(parent.label for parent in self._parents)
                + '\n' + '\n'.join(repr(I) for I in self))

    def __len__(self):
        return len(self._instructions)

    def __iter__(self):
        for I in self._instructions:
            yield I

    def __hash__(self):
        return hash(self.label)

    def __eq__(self, other:BasicBlock):
        # Basic blocks should be uniquely determined by their label
        return self.label == other.label

    @property
    def label(self):
        return self._label

    @property
    def name(self):
        return f"Block{self.label}"

    @property
    def children(self):
        return self._branch_targets.children

    @property
    def branch_condition(self):
        return self._branch_targets.branch_condition

    @property
    def parents(self):
        return tuple(sorted(self._parents, key=lambda B: B.label))

    ### Block modification ###

    def add_parent(self, parent:BasicBlock):
        self._parents.add(parent)

    def remove_parent(self, parent:BasicBlock, ignore_keyerror=False):
        if parent not in self._parents:
            if ignore_keyerror:
                return
            raise KeyError(f"{self.name} does not have a parent at {parent}")
        self._parents.remove(parent)
        parent.remove_child(self.label, ignore_keyerror=True)

    def add_child(self, child:BasicBlock, cond=None, new_child_if_cond=True):
        num_children = len(self.children)
        if num_children == 0:
            if cond is not None:
                raise BranchError(self.label, f"Added branch condition {cond} to unconditional branch out of {self.name}")
            self._branch_targets = BasicBlock._BranchTargets(target=child)
            child.add_parent(self)
            self._instructions.append(GotoInstruction(child.label))
            return
        if num_children == 1:
            if cond is None:
                raise BranchError(self.label, f"Condition required for new branch out of {self.name}")
            first = self.children[0]
            if new_child_if_cond:
                self._branch_targets = BasicBlock._BranchTargets(cond=cond,
                        iftrue=child,
                        iffalse=first)
                self._instructions[-1] = BranchInstruction(cond, child.label, first.label)
            else:
                self._branch_targets = BasicBlock._BranchTargets(cond=cond,
                        iftrue=first,
                        iffalse=child)
                self._instructions[-1] = BranchInstruction(cond, first.label, child.label)
            child.add_parent(self)
            return
        # num_children == 2
        raise BranchError(self.label, f"Cannot have three branch targets out of {self.name}")
    
    def remove_child(self, child:BasicBlock, ignore_keyerror=False):
        if child not in self.children:
            if ignore_keyerror:
                return
            raise KeyError(f"{self.name} does not have {child.label} as child")
        child.remove_parent(self, ignore_keyerror=True)
        if len(self.children) == 1:
            self._instructions.pop() # remove goto statement
            self._branch_targets = BasicBlock._BranchTargets()
            return
        # branch has two children at this point
        kept = self.children[0] if child == self.children[1] else self.children[1]
        self._instructions[-1] = GotoInstruction(kept.label)
        self._branch_targets = BasicBlock._BranchTargets(target=kept)

### Control flow ###

class CFG:

    def __init__(self):
        self._blocks = dict() # str(label) : BasicBlock dictionary
        self._entrypoint = None

    def __len__(self):
        return len(self._blocks)

    def __iter__(self):
        for label in self._blocks:
            yield self._blocks[label]

    def __in__(self, label:str):
        return label in self._blocks

    def __getitem__(self, label:str):
        if label not in self:
            raise KeyError(f"{label} does not label an existing block")

    def _create_block(self, label:str, entrypoint=False):
        if not label.startswith('@'):
            raise ValueError(f"Invalid label {label}: labels must begin with '@'")
        if label in self:
            raise LabelConflictError(f"{label} cannot be assigned to multiple blocks")
        self._blocks[label] = BasicBlock(label)
        if entrypoint:
            if self._entrypoint is not None:
                raise MultipleEntrypointsError
        # all basic blocks are exit nodes by default

    def _fetch_or_create_block(self, label:str):
        if label not in self:
            self._create_block(label)
        return self[label]

    def _populate_block(self, label:str, instructions:list):
        block = self[label]
        for (i, I) in enumerate(instructions):
            if isinstance(I, BranchInstructionClass):
                if i + 1 < len(instructions):
                    raise BranchInBlockException(f"Intermediate instruction {i+1} of block {label} is a branch ({repr(I)})")
                if isinstance(I, GotoInstruction):
                    block.add_child(self._fetch_or_create_block(I.target))
                    return
                if isinstance(I, BranchInstruction):
                    block.add_child(self._fetch_or_create_block(I.iftrue))
                    block.add_child(self._fetch_or_create_block(I.iffalse),
                            cond=I.cond, new_child_if_cond=False)
                    return
            self[label]._instructions.append(I)
      
    def add_block(self, label:str, instructions:list, entrypoint=False):
        self._create_block(self, label, entrypoint=entrypoint)
        self._populate_block(self, label, instructions)

    def remove_block(self, label:str, ignore_keyerror=False):
        if label not in self:
            if ignore_keyerror:
                return
            raise KeyError(f"Attempting to remove non-existing block at {label}")
        block = self[label]
        for parent in block.parents:
            parent.remove_child(block)
        for child in block.children:
            child.remove_parent(child)

        del self._blocks[label]

    def assert_completeness(self, fix_lost_parents=False):
        """
        Assert that all children know their parents and vice versa
        """
        for label in self:
            block = self[label]
            for child in block.children:
                if block not in child.parents:
                    if fix_lost_parents:
                        child.add_parent(block)
                        continue
                    raise LostParentError(f"{child.label} does not know of parent block {parent.label}")
            for parent in block.parents:
                if block not in parent.children:
                    raise LostChildError(f"{parent.label} does not know of child block {child.label}")

### Error classes ###

class BranchError(Exception):
    def __init__(self, block_label, message=""):
        self.block_label = block_label
        self.message = message
        super().__init__(message)

class LabelConflictError(Exception):
    def __init__(self, message=""):
        self.message = message
        super().__init__(message)

class MultipleEntrypointsError(Exception):
    def __init__(self, message=""):
        self.message = message
        super().__init__(message)

class LostParentError(Exception):
    def __init__(self, message=""):
        self.message = message
        super().__init__(message)

class LostChildError(Exception):
    def __init__(self, message=""):
        self.message = message
        super().__init__(message)
