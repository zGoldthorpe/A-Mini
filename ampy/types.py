"""
A-Mi types
============
Goldthorpe

This module contains the abstract types necessary for encoding an A-Mi program

An A-Mi program is stored abstractly as a control flow graph of basic blocks,
where each basic block consists of several InstructionClass instances ending with
an instruction of the BranchInstructionClass subclass.
"""

from ampy.ensuretypes import Syntax

### Instructions ###

class InstructionClass:
    """
    Parent instruction type
    """
    def __repr__(self):
        raise NotImplementedError("Every instruction must override this method.")

### General instruction classes ###

class ArithInstructionClass(InstructionClass):
    @(Syntax(object, str, str, str, str) >> None)
    def __init__(self, op, res, op1, op2):
        self.target = res
        self.op = op
        self.operands = (op1, op2)

    def __repr__(self):
        return f"{self.target} = {self.operands[0]} {self.op} {self.operands[1]}"

class CompInstructionClass(InstructionClass):
    @(Syntax(object, str, str, str, str) >> None)
    def __init__(self, cmp, res, op1, op2):
        self.target = res
        self.cmp = cmp
        self.operands = (op1, op2)

    def __repr__(self):
        return f"{self.target} = {self.operands[0]} {self.cmp} {self.operands[1]}"

class BranchInstructionClass(InstructionClass):
    pass

### Instruction types ###

class MovInstruction(InstructionClass):
    @(Syntax(object, str, str) >> None)
    def __init__(self, lhs, rhs):
        self.target = lhs
        self.operand = rhs

    def __repr__(self):
        return f"{self.target} = {self.operand}"

class PhiInstruction(InstructionClass):
    @(Syntax(object, str, [str, 2], ...) >> None)
    def __init__(self, lhs, *conds):
        self.target = lhs
        self.conds = conds

    def __repr__(self):
        return f"{self.target} = phi " + ", ".join(f"[ {val}, {lbl} ]" for val, lbl in self.conds)

class AddInstruction(ArithInstructionClass):
    @(Syntax(object, str, str, str) >> None)
    def __init__(self, dest, op1, op2):
        super().__init__('+', dest, op1, op2)

class SubInstruction(ArithInstructionClass):
    @(Syntax(object, str, str, str) >> None)
    def __init__(self, dest, op1, op2):
        super().__init__('-', dest, op1, op2)

class MulInstruction(ArithInstructionClass):
    @(Syntax(object, str, str, str) >> None)
    def __init__(self, dest, op1, op2):
        super().__init__('*', dest, op1, op2)

class EqInstruction(CompInstructionClass):
    @(Syntax(object, str, str, str) >> None)
    def __init__(self, dest, op1, op2):
        super().__init__("==", dest, op1, op2)

class NeqInstruction(CompInstructionClass):
    @(Syntax(object, str, str, str) >> None)
    def __init__(self, dest, op1, op2):
        super().__init__("!=", dest, op1, op2)

class LtInstruction(CompInstructionClass):
    @(Syntax(object, str, str, str) >> None)
    def __init__(self, dest, op1, op2):
        super().__init__("<", dest, op1, op2)

class LeqInstruction(CompInstructionClass):
    @(Syntax(object, str, str, str) >> None)
    def __init__(self, dest, op1, op2):
        super().__init__("<=", dest, op1, op2)

class GotoInstruction(BranchInstructionClass):
    @(Syntax(object, str) >> None)
    def __init__(self, tgt):
        self.target = tgt

    def __repr__(self):
        return f"goto {self.target}"

class BranchInstruction(BranchInstructionClass):
    @(Syntax(object, str, str, str)
      | Syntax(object, cond=str, iftrue=str, iffalse=str)
      >> None)
    def __init__(self, cond, iftrue, iffalse):
        self.cond = cond
        self.iftrue = iftrue
        self.iffalse = iffalse

    def __repr__(self):
        return f"branch {self.cond} ? {self.iftrue} : {self.iffalse}"

class ExitInstruction(BranchInstructionClass):
    @(Syntax(object) >> None)
    def __init__(self):
        pass

    def __repr__(self):
        return "exit"

class ReadInstruction(InstructionClass):
    @(Syntax(object, str) >> None)
    def __init__(self, lhs):
        self.target = lhs

    def __repr__(self):
        return f"read {self.target}"

class WriteInstruction(InstructionClass):
    @(Syntax(object, str) >> None)
    def __init__(self, lhs):
        self.target = lhs

    def __repr__(self):
        return f"write {self.target}"

class BrkInstruction(InstructionClass):
    @(Syntax(object, str) >> None)
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"brkpt !{self.name}"

### Basic blocks ###

# forward declarations
class BasicBlock:
    pass
class BranchTargets:
    pass

class BranchTargets(BranchTargets):
    @(Syntax(object) # exit note; no children
      | Syntax(object, BasicBlock) # goto
      | Syntax(object, target=BasicBlock) # goto with kwarg
      | Syntax(object, cond=str, iftrue=BasicBlock, iffalse=BasicBlock) # branch
      >> None)
    def __init__(self, target=None, cond=None, iftrue=None, iffalse=None):
        self._target = target
        self._cond = cond
        self._iftrue = iftrue
        self._iffalse = iffalse

    @(Syntax(object, BranchTargets) >> bool)
    def __eq__(self, other):
        return (self._target == other._target
                and self._cond == other._cond
                and self._iftrue == other._iftrue
                and self._iffalse == other._iffalse)

    def __len__(self):
        return (2 if self._cond is not None
                else 1 if self._target is not None
                else 0)

    @(Syntax(object) >> {BasicBlock})
    def __iter__(self):
        if self._cond is not None:
            yield self._iftrue
            yield self._iffalse
        elif self._target is not None:
            yield self._target
        # empty yield otherwise

    @(Syntax(object, BasicBlock) >> bool)
    def __in__(self, block):
        return block in self.tuple

    @(Syntax(object, int) >> BasicBlock)
    def __getitem__(self, idx):
        return self.tuple[idx]
    
    def __repr__(self):
        if self._cond is not None:
            return f"BranchTargets({self._iftrue.name} if {self._cond} else {self._iffalse.name})"
        if self._target is not None:
            return f"BranchTargets({self._target.name})"
        return "BranchTargets()"
    
    @property
    @(Syntax(object) >> [tuple, BasicBlock, [0, 2]])
    def tuple(self):
        if self._cond is not None:
            return (self._iftrue, self._iffalse)
        if self._target is not None:
            return (self._target,)
        return ()

    @property
    @(Syntax(object) >> (str, None))
    def branch_condition(self):
        return self._cond

    @property
    @(Syntax(object) >> InstructionClass)
    def instruction(self):
        if self._cond is not None:
            return BranchInstruction(cond=self._cond, iftrue=self._iftrue.label, iffalse=self._iffalse.label)
        if self._target is not None:
            return GotoInstruction(self._target.label)
        return ExitInstruction()

class BasicBlock(BasicBlock):

    @(Syntax(object, str, InstructionClass, ...) >> None)
    def __init__(self, label:str, *instructions):
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
                + '\n' + '\n'.join(repr(I) for I in self))

    def __len__(self):
        return len(self._instructions) + 1
        # the + 1 is for the branch instruction

    @(Syntax(object) >> {InstructionClass})
    def __iter__(self):
        for I in self._instructions:
            yield I
        yield self.branch_instruction

    @(Syntax(object, int) >> InstructionClass)
    def __getitem__(self, index):
        if index < 0:
            index += len(self._instructions) + 1
        if index > len(self._instructions) or index < 0:
            raise IndexError
        if index == len(self._instructions):
            return self.branch_instruction
        return self._instructions[index]

    def __hash__(self):
        return hash(self.label)

    @(Syntax(object, (BasicBlock, None)) >> bool)
    def __eq__(self, other):
        # Basic blocks should be uniquely determined by their label
        if other is None:
            return False
        return self.label == other.label

    @property
    @(Syntax(object) >> str)
    def label(self):
        return self._label

    @property
    @(Syntax(object) >> str)
    def name(self):
        return f"Block{self.label}"

    @property
    @(Syntax(object) >> BranchTargets)
    def children(self):
        return self._branch_targets

    @property
    @(Syntax(object) >> [set, BasicBlock])
    def parents(self):
        return set(self._parents)

    @property
    @(Syntax(object) >> InstructionClass)
    def branch_instruction(self):
        return self._branch_targets.instruction

    ### Block modification ###

    @(Syntax(object, BasicBlock) >> None)
    def add_parent(self, parent):
        self._parents.add(parent)

    @(Syntax(object, BasicBlock, ignore_keyerror=bool, propagate=bool) >> None)
    def remove_parent(self, parent, ignore_keyerror=False, propagate=True):
        if parent not in self._parents:
            if ignore_keyerror:
                return
            raise KeyError(f"{self.name} does not have a parent at {parent}")
        self._parents.remove(parent)
        if propagate:
            parent.remove_child(self, ignore_keyerror=True, propagate=False)

    @(Syntax(object, BasicBlock) # if no existing children
      | Syntax(object, BasicBlock, cond=str) # if new child is true target
      | Syntax(object, BasicBlock, cond=str, new_child_if_cond=bool)
      >> None)
    def add_child(self, child, cond=None, new_child_if_cond=True):
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
    
    @(Syntax(object, BasicBlock, ignore_keyerror=bool, propagate=bool, keep_duplicate=bool) >> None)
    def remove_child(self, child, ignore_keyerror=False, propagate=True, keep_duplicate=False):
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

    @(Syntax(object) >> None)
    def __init__(self):
        self._blocks = dict() # str(label) : BasicBlock dictionary
        self._undef_blocks = dict()
        self._entrypoint = None

    def __repr__(self):
        return ("Control Flow Graph:\nEntry point: "
                + (self.entrypoint.label
                    if self.entrypoint is not None
                    else "<not set>") + "\n\n"
                + "\n\n".join(("(?)" if block.label in self._undef_blocks
                                else "") + repr(block) for block in self))

    def __len__(self):
        return len(self._blocks)

    @(Syntax(object) >> {BasicBlock})
    def __iter__(self):
        for label in self._blocks:
            yield self._blocks[label]

    @(Syntax(object, str) >> BasicBlock)
    def __getitem__(self, label):
        if label not in self.labels:
            raise KeyError(f"{label} does not label an existing block")
        return self._blocks[label]

    @property
    @(Syntax(object) >> [set, str])
    def labels(self):
        return set(self._blocks.keys())

    @property
    @(Syntax(object) >> {BasicBlock})
    def blocks(self):
        for label in self._blocks:
            if label not in self._undef_blocks:
                yield self._blocks[label]

    @property
    @(Syntax(object) >> {BasicBlock})
    def undefined_blocks(self):
        for label in self._undef_blocks:
            yield self._blocks[label]

    @(Syntax(object, str) >> None)
    def _create_block(self, label):
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

    @(Syntax(object, str) >> BasicBlock)
    def _fetch_or_create_block(self, label):
        if label not in self.labels:
            self._create_block(label)
            self._undef_blocks[label] = self[label]
            # block does not exist, so buffer a new one as "undefined"
        return self[label]

    @(Syntax(object, str, InstructionClass, ...) >> None)
    def _populate_block(self, label, *instructions):
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

    @(Syntax(object, str) >> None)
    def set_entrypoint(self, label):
        self._entrypoint = self._fetch_or_create_block(label)

    @property
    @(Syntax(object) >> BasicBlock)
    def entrypoint(self):
        return self._entrypoint

    @(Syntax(object, str, InstructionClass, ...) >> None)
    def add_block(self, label, *instructions):
        """
        Add the instructions for a single basic block to the CFG.
        Intermediate instructions cannot be branches.
        If final instruction is not a branch, then block is assumed to be
        an exit node.
        """
        self._create_block(label)
        self._populate_block(label, *instructions)

    @(Syntax(object, str, ignore_keyerror=bool) >> None)
    def remove_block(self, label, ignore_keyerror=False):
        """
        Remove block of given label from CFG
        """
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

    @(Syntax(object, fix_lost_parents=bool) >> None)
    def assert_completeness(self, fix_lost_parents=False):
        """
        Assert that all children know their parents and vice versa
        """
        for block in self:
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
