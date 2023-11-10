"""
A-Mi types
============
Goldthorpe

This module contains the abstract types necessary for encoding an A-Mi program

An A-Mi program is stored abstractly as a control flow graph of basic blocks,
where each basic block consists of several InstructionClass instances ending with
an instruction of the BranchInstructionClass subclass.
"""

from ampy.ensuretypes import Syntax, TypedDict

### Metadata ###

class MetaDict(TypedDict):
    """
    Lazy type-checked metadata dictionary
    """
    @(Syntax(object, dc={str:((list,[str]),None)})
      | Syntax(object, {str:((list,[str]),None)})
      >> None)
    def __init__(self, dc={}):
        super().__init__(dc, str, ((list,[str]), None))

### Instructions ###

class InstructionClass:
    """
    Parent instruction type
    """
    @(Syntax(object) >> None)
    def __init__(self):
        self.meta = MetaDict()

    def __repr__(self):
        raise NotImplementedError("Every instruction must override this method.")

### General instruction classes ###

class DefInstructionClass(InstructionClass):
    """
    Instruction class for all instructions that assign a value
    to a register
    """
    @(Syntax(object, str) >> None)
    def __init__(self, target):
        self.target = target
        super().__init__()

class BinaryInstructionClass(DefInstructionClass):
    """
    Instruction class for all instructions that compute
    a binary operation
    """
    @(Syntax(object, str, str, str, str) >> None)
    def __init__(self, op, res, op1, op2):
        self.op = op
        self.operands = (op1, op2)
        super().__init__(res)

    def __repr__(self):
        return f"{self.target} = {self.operands[0]} {self.op} {self.operands[1]}"

class ArithInstructionClass(BinaryInstructionClass):
    pass

class CompInstructionClass(BinaryInstructionClass):
    pass

class BranchInstructionClass(InstructionClass):
    @(Syntax(object) >> None)
    def __init__(self):
        super().__init__()

### Instruction types ###

class MovInstruction(DefInstructionClass):
    @(Syntax(object, str, str) >> None)
    def __init__(self, lhs, rhs):
        self.operand = rhs
        super().__init__(lhs)

    def __repr__(self):
        return f"{self.target} = {self.operand}"

class PhiInstruction(DefInstructionClass):
    @(Syntax(object, str, [str, 2], ...) >> None)
    def __init__(self, lhs, *conds):
        self.conds = conds
        super().__init__(lhs)

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
        super().__init__()

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
        super().__init__()

    def __repr__(self):
        return f"branch {self.cond} ? {self.iftrue} : {self.iffalse}"

class ExitInstruction(BranchInstructionClass):
    @(Syntax(object) >> None)
    def __init__(self):
        super().__init__()

    def __repr__(self):
        return "exit"

class ReadInstruction(DefInstructionClass):
    @(Syntax(object, str) >> None)
    def __init__(self, lhs):
        super().__init__(lhs)

    def __repr__(self):
        return f"read {self.target}"

class WriteInstruction(InstructionClass):
    @(Syntax(object, str) >> None)
    def __init__(self, rhs):
        self.operand = rhs
        super().__init__()

    def __repr__(self):
        return f"write {self.operand}"

class BrkInstruction(InstructionClass):
    @(Syntax(object, str) >> None)
    def __init__(self, name):
        self.name = name
        super().__init__()

    def __repr__(self):
        return f"brkpt !{self.name}"

### Basic blocks ###

# forward declarations
class BasicBlock:
    pass
class CFG:
    pass

class BasicBlock(BasicBlock):

    @(Syntax(object, CFG, str, InstructionClass, ...) >> None)
    def __init__(self, cfg, label:str, *instructions):
        """
        label: string @label indicating block's "name"
        instructions: list of Instruction objects, EXCLUDING the branch at the end
        (children / parents determined after initialisation)
        """
        self._cfg = cfg
        self._label = label
        self._instructions = list(instructions)
        self._parents = set()
        self.meta = MetaDict()

    def __repr__(self):
        return (f"{self.name}\n{'':->{len(self.name)}}\n"
                + "parents: " + ", ".join(parent.label for parent in sorted(self._parents, key=lambda p: p.label))
                + '\n' + '\n'.join(repr(I) for I in self))

    def __len__(self):
        self.branch_instruction
        return len(self._instructions)

    @(Syntax(object) >> [iter, InstructionClass])
    def __iter__(self):
        for I in self._instructions:
            yield I

    @property
    @(Syntax(object) >> [InstructionClass])
    def instructions(self):
        return [I for I in self]

    @(Syntax(object, int) >> InstructionClass)
    def __getitem__(self, index):
        self.branch_instruction # ensure the branch instruction exists
        if index < 0:
            index += len(self._instructions)
        if index >= len(self._instructions) or index < 0:
            raise IndexError
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
    @(Syntax(object) >> [tuple, BasicBlock])
    def children(self):
        if isinstance(self.branch_instruction, ExitInstruction):
            return ()
        if isinstance(self.branch_instruction, GotoInstruction):
            return (self._cfg[self.branch_instruction.target],)
        return (self._cfg[self.branch_instruction.iffalse], self._cfg[self.branch_instruction.iftrue])

    @property
    @(Syntax(object) >> [set, BasicBlock])
    def parents(self):
        return set(self._parents)

    @property
    @(Syntax(object) >> InstructionClass)
    def branch_instruction(self):
        if len(self._instructions) == 0 or not isinstance(self._instructions[-1], BranchInstructionClass):
            self._instructions.append(ExitInstruction())
        return self._instructions[-1]

    ### Block modification ###

    @(Syntax(object, BasicBlock) >> None)
    def add_parent(self, parent):
        self._parents.add(parent)

    @(Syntax(object, BasicBlock, ignore_keyerror=bool, propagate=bool) >> None)
    def remove_parent(self, parent, ignore_keyerror=False, propagate=True):
        if parent not in self._parents:
            if ignore_keyerror:
                return
            raise KeyError(f"{self.name} does not have a parent {parent.name}")
        self._parents.remove(parent)
        if propagate:
            parent.remove_child(self, ignore_keyerror=True, propagate=False)

    @(Syntax(object, BasicBlock) # if no existing children
      | Syntax(object, BasicBlock, cond=str) # if new child is true target
      | Syntax(object, BasicBlock, cond=str, new_child_if_cond=bool)
      >> None)
    def add_child(self, child, cond=None, new_child_if_cond=True):
        children = self.children
        branch = self._instructions.pop()
        if len(children) == 0:
            if cond is not None:
                raise BranchError(self.label, f"Added branch condition {cond} to unconditional branch out of {self.name}")
            self._instructions.append(GotoInstruction(child.label))
            self._instructions[-1].meta = branch.meta
            child.add_parent(self)
            return
        if len(children) == 1:
            if cond is None:
                raise BranchError(self.label, f"Condition required for new branch out of {self.name}")
            first = children[0]
            if new_child_if_cond:
                self._instructions.append(BranchInstruction(cond=cond,
                            iftrue=child.label,
                            iffalse=first.label))
            else:
                self._instructions.append(BranchInstruction(cond=cond,
                            iftrue=first.label,
                            iffalse=child.label))

            self._instructions[-1].meta = branch.meta
            child.add_parent(self)
            return
        # len(children) == 2
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
        children = self.children
        branch = self._instructions.pop()

        if len(children) == 1:
            self._instructions.append(ExitInstruction())
            self._instructions[-1].meta = branch.meta
            return
        # branch has two children at this point
        kept = children[0] if child == children[1] else children[1]
        if kept == child:
            if keep_duplicate:
                kept.add_parent(self)
                # since kept == child, its parent was deleted already
            else:
                self._instructions.append(ExitInstruction())
                self._instructions[-1].meta = branch.meta
                # remove both child and duplicate
                return
        self._instructions.append(GotoInstruction(kept.label))
        self._instructions[-1].meta = branch.meta

    @(Syntax(object) >> None)
    def remove_children(self, propagate=True):
        """
        Removes all branch targets for current block.
        """
        children = self.children
        for child in children:
            self.remove_child(child, propagate=propagate)

### Control flow ###

class CFG(CFG):

    @(Syntax(object) >> None)
    def __init__(self):
        self._blocks = dict() # str(label) : BasicBlock dictionary
        self._undef_blocks = dict()
        self._entrypoint = None
        self.meta = MetaDict()

    def __repr__(self):
        return ("Control Flow Graph:\nEntry point: "
                + (self.entrypoint.label
                    if self.entrypoint is not None
                    else "<not set>") + "\n\n"
                + "\n\n".join(("(?)" if block.label in self._undef_blocks
                                else "") + repr(block) for block in self))

    def __len__(self):
        return len(self._blocks)

    @(Syntax(object) >> [iter, BasicBlock])
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
    @(Syntax(object) >> [iter, BasicBlock])
    def blocks(self):
        for label in self._blocks:
            if label not in self._undef_blocks:
                yield self._blocks[label]

    @property
    @(Syntax(object) >> [iter, BasicBlock])
    def undefined_blocks(self):
        for label in self._undef_blocks:
            yield self._blocks[label]

    @(Syntax(object, str) >> None)
    def create_block(self, label):
        """
        Create a new block, removing it from the list of "undefined" blocks if necessary
        """
        if not label.startswith('@'):
            raise ValueError(f"Invalid label {label}: labels must begin with '@'")
        if label in self.labels:
            if label in self._undef_blocks:
                # block has been instantiated for a jump, but is undefined
                del self._undef_blocks[label]
                return
            raise LabelConflictError(f"{label} cannot be assigned to multiple blocks")
        self._blocks[label] = BasicBlock(self, label)
        # all basic blocks are exit nodes by default

    @(Syntax(object, str) >> BasicBlock)
    def fetch_or_create_block(self, label):
        """
        Grab block if it exists, or else implicitly create a new "undefined" one.
        """
        if label not in self.labels:
            self.create_block(label)
            self._undef_blocks[label] = self[label]
            # block does not exist, so buffer a new one as "undefined"
        return self[label]

    @(Syntax(object, str, InstructionClass, ...) >> None)
    def populate_block(self, label, *instructions):
        """
        Clears block instructions and populates it with passed instructions
        """
        block = self[label]
        block._instructions = [] # empty instructions
        for (i, I) in enumerate(instructions):
            if isinstance(I, BranchInstructionClass):
                if i + 1 < len(instructions):
                    raise BranchInBlockException(f"Intermediate instruction {i+1} of block {label} is a branch ({repr(I)})")
                # pass metadata before interpreting branch
                block.branch_instruction.meta = I.meta

                if isinstance(I, ExitInstruction):
                    return
                if isinstance(I, GotoInstruction):
                    block.add_child(self.fetch_or_create_block(I.target))
                    return
                if isinstance(I, BranchInstruction):
                    block.add_child(self.fetch_or_create_block(I.iftrue))
                    block.add_child(self.fetch_or_create_block(I.iffalse),
                            cond=I.cond, new_child_if_cond=False)
                    return
            block._instructions.append(I)

    @(Syntax(object, str) >> None)
    def set_entrypoint(self, label):
        self._entrypoint = self.fetch_or_create_block(label)

    @property
    @(Syntax(object) >> (BasicBlock, None))
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
        self.create_block(label)
        self.populate_block(label, *instructions)

    @(Syntax(object, str, ignore_keyerror=bool) >> None)
    def remove_block(self, label, ignore_keyerror=False):
        """
        Remove block of given label from CFG
        """
        if label not in self.labels:
            if ignore_keyerror:
                return
            raise KeyError(f"Attempting to remove non-existing block at {label}")
        block = self[label]
        for parent in block.parents:
            parent.remove_child(block, ignore_keyerror=ignore_keyerror)
        for child in block.children:
            child.remove_parent(block, ignore_keyerror=ignore_keyerror)

        if self._entrypoint == block:
            self._entrypoint = None

        del self._blocks[label]

    @(Syntax(object) >> None)
    def tidy(self):
        """
        Clean up CFG.
        Remove unreachable blocks, test phi nodes, and ensure all
        children know all parents
        """
        untouched = {block for block in self}
        def dfs(block):
            untouched.remove(block)
            for child in block.children:
                if block not in child.parents:
                    child.add_parent(block)
                if child in untouched:
                    dfs(child)

        dfs(self.entrypoint)

        for block in untouched:
            self.remove_block(block.label, ignore_keyerror=True)

        for block in self:
            for parent in block.parents:
                if block not in parent.children:
                    raise LostChildError(f"{parent.label} does not know of child block {block.label}")

            parent_labels = {parent.label for parent in block.parents}
            instructions = enumerate(block)
            for i, I in instructions:
                if isinstance(I, PhiInstruction):
                    # we will just passively clean up phi nodes
                    I.conds = tuple(filter(
                        lambda p: p[1] in parent_labels,
                        I.conds))
                    lbls = {lbl for _, lbl in I.conds}
                    if len(lbls) < len(I.conds):
                        raise BadPhiError(block, i, f"Phi node in {block.label}:{i} has repeated labels.")
                    if len(diff := parent_labels - {lbl for _, lbl in I.conds}) > 0:
                        raise BadPhiError(block, i, f"Phi node in {block.label}:{i} missing a value for {', '.join(sorted(diff))}")
                    if len(I.conds) == 1:
                        block._instructions[i] = MovInstruction(I.target, I.conds[0][0])
                        block[i].meta = I.meta



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

class LostChildError(Exception):
    def __init__(self, message=""):
        self.message = message
        super().__init__(message)

class BadPhiError(Exception):
    def __init__(self, block, index, message=""):
        self.message = message
        super().__init__(message)
