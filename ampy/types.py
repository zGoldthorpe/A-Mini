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
    def __init__(self, lhs, *conds):
        self.target = lhs
        self.conds = conds
        super().__init__(f"{lhs} = phi " + ", ".join(f"[ {val}, {lbl} ]" for val, lbl in conds), "move")

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
    def __init__(self, target:str):
        super().__init__(f"goto {target}")
        self.target = target

class BranchInstruction(BranchInstructionClass):
    def __init__(self, cond:str, iftrue:str, iffalse:str):
        super().__init__(f"if ({cond}) goto {iftrue} else goto {iffalse}")
        self.cond = cond
        self.iftrue = iftrue
        self.iffalse = iffalse

class ExitInstruction(BranchInstructionClass):
    def __init__(self):
        super().__init__("exit")

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

# forward declarations
class BasicBlock:
    pass
class BranchTargets:
    pass

class BranchTargets(BranchTargets):
    @ensure_multi(
            Syntax(object), # exit node; no children
            Syntax(object, target=BasicBlock), # goto
            Syntax(object, cond=str, iftrue=BasicBlock, iffalse=BasicBlock)) # branch
    def __init__(self, target=None, cond=None, iftrue=None, iffalse=None):
        self._target = target
        self._cond = cond
        self._iftrue = iftrue
        self._iffalse = iffalse

    @ensure_types(object, BranchTargets)
    def __eq__(self, other):
        return (self._target == other._target
                and self._cond == other._cond
                and self._iftrue == other._iftrue
                and self._iffalse == other._iffalse)

    def __len__(self):
        return (2 if self._cond is not None
                else 1 if self._target is not None
                else 0)

    def __iter__(self):
        if self._cond is not None:
            yield self._iftrue
            yield self._iffalse
        elif self._target is not None:
            yield self._target
        # empty yield otherwise

    @ensure_types(object, BasicBlock)
    def __in__(self, block):
        return block in self.tuple

    @ensure_types(object, int)
    def __getitem__(self, idx):
        return self.tuple[idx]
    
    def __repr__(self):
        if self._cond is not None:
            return f"BranchTargets({self._iftrue.name} if {self._cond} else {self._iffalse.name})"
        if self._target is not None:
            return f"BranchTargets({self._target.name})"
        return "BranchTargets()"
    
    @property
    def tuple(self):
        if self._cond is not None:
            return (self._iftrue, self._iffalse)
        if self._target is not None:
            return (self._target,)
        return ()

    @property
    def branch_condition(self):
        return self._cond

    @property
    def instruction(self):
        if self._cond is not None:
            return BranchInstruction(cond=self._cond, iftrue=self._iftrue.label, iffalse=self._iffalse.label)
        if self._target is not None:
            return GotoInstruction(target=self._target.label)
        return ExitInstruction()

class BasicBlock(BasicBlock):

    def __init__(self, label:str, instructions:list=[]):
        """
        label: string @label indicating block's "name"
        instructions: list of Instruction objects, EXCLUDING the branch at the end
        (children / parents determined after initialisation)
        """
        self._label = label
        self._instructions = list(instructions)
        self._branch_targets = BranchTargets()
        self._parents = set()

    def __repr__(self):
        return (f"{self.name}\n{'':->{len(self.name)}}\n"
                + "parents: " + ", ".join(parent.label for parent in sorted(self._parents, key=lambda p: p.label))
                + '\n' + '\n'.join(repr(I) for I in self)
                + '\n' + repr(self.branch_instruction))

    def __len__(self):
        return len(self._instructions)

    def __iter__(self):
        for I in self._instructions:
            yield I

    def __hash__(self):
        return hash(self.label)

    @ensure_types(object, (BasicBlock, type(None)))
    def __eq__(self, other:BasicBlock):
        # Basic blocks should be uniquely determined by their label
        if other is None:
            return False
        return self.label == other.label

    @property
    def label(self):
        return self._label

    @property
    def name(self):
        return f"Block{self.label}"

    @property
    def children(self):
        return self._branch_targets

    @property
    def parents(self):
        return set(self._parents)

    @property
    def branch_instruction(self):
        return self._branch_targets.instruction

    ### Block modification ###

    def add_parent(self, parent:BasicBlock):
        self._parents.add(parent)

    def remove_parent(self, parent:BasicBlock, ignore_keyerror=False, propagate=True):
        if parent not in self._parents:
            if ignore_keyerror:
                return
            raise KeyError(f"{self.name} does not have a parent at {parent}")
        self._parents.remove(parent)
        if propagate:
            parent.remove_child(self, ignore_keyerror=True, propagate=False)

    def add_child(self, child:BasicBlock, cond=None, new_child_if_cond=True):
        num_children = len(self.children)
        if num_children == 0:
            if cond is not None:
                raise BranchError(self.label, f"Added branch condition {cond} to unconditional branch out of {self.name}")
            self._branch_targets = BranchTargets(target=child)
            child.add_parent(self)
            return
        if num_children == 1:
            if cond is None:
                raise BranchError(self.label, f"Condition required for new branch out of {self.name}")
            first = self.children[0]
            if new_child_if_cond:
                self._branch_targets = BranchTargets(cond=cond,
                        iftrue=child,
                        iffalse=first)
            else:
                self._branch_targets = BranchTargets(cond=cond,
                        iftrue=first,
                        iffalse=child)
            child.add_parent(self)
            return
        # num_children == 2
        raise BranchError(self.label, f"Cannot have three branch targets out of {self.name}")
    
    def remove_child(self, child:BasicBlock, ignore_keyerror=False, propagate=True, keep_duplicate=False):
        """
        Removes child as branch target for current block.
        """
        if child not in self.children:
            if ignore_keyerror:
                return
            raise KeyError(f"{self.name} does not have {child.label} as child")
        if propagate:
            child.remove_parent(self, ignore_keyerror=True, propagate=False)
        if len(self.children) == 1:
            self._branch_targets = BranchTargets()
            return
        # branch has two children at this point
        kept = self.children[0] if child == self.children[1] else self.children[1]
        if kept == child:
            if keep_duplicate:
                kept.add_parent(self)
                # since kept == child, its parent was deleted already
            else:
                self._branch_targets = BranchTargets()
                # remove both child and duplicate
                return
        self._branch_targets = BranchTargets(target=kept)

### Control flow ###

class CFG:

    def __init__(self):
        self._blocks = dict() # str(label) : BasicBlock dictionary
        self._undef_blocks = dict()
        self._entrypoint = None

    def __repr__(self):
        return ("Control Flow Graph:\nEntry point: "
                + (self.entrypoint.label
                    if self.entrypoint is not None
                    else "<not set>") + '\n'
                + "\n\n".join(("(?)" if block.label in self._undef_blocks
                                else "") + repr(block) for block in self))

    def __len__(self):
        return len(self._blocks)

    def __iter__(self):
        for label in self._blocks:
            yield self._blocks[label]

    def __getitem__(self, label:str):
        if label not in self.labels:
            raise KeyError(f"{label} does not label an existing block")
        return self._blocks[label]

    @property
    def labels(self):
        return set(self._blocks.keys())

    @property
    def blocks(self):
        for label in self._blocks:
            yield self._blocks[label]

    @property
    def undefined_blocks(self):
        for label in self._undef_blocks:
            yield self._blocks[label]

    def _create_block(self, label:str):
        if not label.startswith('@'):
            raise ValueError(f"Invalid label {label}: labels must begin with '@'")
        if label in self.labels:
            if label in self._undef_blocks:
                # block has been instantiated for a jump, but is undefined
                del self._undef_blocks[label]
                return
            raise LabelConflictError(f"{label} cannot be assigned to multiple blocks")
        self._blocks[label] = BasicBlock(label)
        # all basic blocks are exit nodes by default

    def _fetch_or_create_block(self, label:str):
        if label not in self.labels:
            self._create_block(label)
            self._undef_blocks[label] = self[label]
            # block does not exist, so buffer a new one as "undefined"
        return self[label]

    def _populate_block(self, label:str, *instructions):
        block = self[label]
        for (i, I) in enumerate(instructions):
            if isinstance(I, BranchInstructionClass):
                if i + 1 < len(instructions):
                    raise BranchInBlockException(f"Intermediate instruction {i+1} of block {label} is a branch ({repr(I)})")
                if isinstance(I, ExitInstruction):
                    return
                if isinstance(I, GotoInstruction):
                    block.add_child(self._fetch_or_create_block(I.target))
                    return
                if isinstance(I, BranchInstruction):
                    block.add_child(self._fetch_or_create_block(I.iftrue))
                    block.add_child(self._fetch_or_create_block(I.iffalse),
                            cond=I.cond, new_child_if_cond=False)
                    return
            self[label]._instructions.append(I)

    def set_entrypoint(self, label:str):
        self._entrypoint = self._fetch_or_create_block(label)

    @property
    def entrypoint(self):
        return self._entrypoint

    def add_block(self, label:str, *instructions):
        self._create_block(label)
        self._populate_block(label, *instructions)

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

        if self._entrypoint == block:
            self._entrypoint = None

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
