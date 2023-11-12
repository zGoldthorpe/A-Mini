"""
Branch elimination
====================
Goldthorpe

This pass simplifies branches and merges basic blocks where possible.
"""

from ampy.ensuretypes import Syntax

from opt.tools import Opt

import ampy.types
import ampy.debug

class BranchElim(Opt):
    # forward declaration
    pass

class BranchElim(BranchElim):
    """
    branch-elim

    Simplifies control flow graph: simplifies branches, and merges
    basic blocks where possible.
    """

    @BranchElim.init("branch-elim")
    def __init__(self, /):
        pass

    @BranchElim.opt_pass
    def simplify(self):
        """
        CFG simplification
        """
        changed = False

        while True:
            ampy.debug.print(self.ID, "cycling through blocks")
            reduced = False

            blocks = set(self.CFG)
            for block in blocks:
                if isinstance(block[-1], ampy.types.ExitInstruction):
                    continue
                if isinstance(block[-1], ampy.types.BranchInstruction):
                    if block[-1].cond.startswith('%'):
                        if block[-1].iftrue == block[-1].iffalse:
                            reduced = True
                            block.remove_child(self.CFG[block[-1].iftrue], keep_duplicate=True)
                    elif block[-1].cond == '0':
                        reduced = True
                        block.remove_child(self.CFG[block[-1].iftrue])
                    else: # block[-1].cond is a nonzero constant
                        reduced = True
                        block.remove_child(self.CFG[block[-1].iffalse])
                if isinstance(block[-1], ampy.types.BranchInstruction):
                    continue
                
                # at this point, block ends with a goto
                child = block.children[0]

                if len(child.parents) == 1:
                    # we can merge the child with the block at no risk
                    ampy.debug.print(self.ID, f"Merging {child.label} with its parent {block.label}")
                    reduced = True
                    block._instructions.pop() 
                    for I in child:
                        block._instructions.append(I)
                    for grandchild in child.children:
                        grandchild.add_parent(block)
                        for I in grandchild:
                            if isinstance(I, ampy.types.PhiInstruction):
                                # it's impossible for phi to depend on block
                                # before merge, as block only has one child
                                I.conds = tuple(map(lambda p: (p[0], p[1] if p[1] != child.label else block.label), I.conds))
                    self.CFG.remove_block(child.label, ignore_keyerror=True)

                elif len(block) == 1:
                    # in order to be allowed to merge an empty block with
                    # its child, we have to be sure that the child does not
                    # have any phi nodes that depend on control flow; e.g.
                    # @0: branch %c ? @1 : @2
                    # @1: goto @2
                    # @2: %x = [ 0, @0 ], [ 1, @1 ]
                    # In this case, @1 cannot be merged up or down
                    can_merge = True

                    for I in child:
                        if isinstance(I, ampy.types.PhiInstruction):
                            # A phi node in child is non-problematic if it does not
                            # depend inconsistently on block and block's parents;
                            # in this case, we can replace the phi condition on block
                            # with a copy of this phi condition on each of the block's
                            # parents.
                            # This only fails if a block has no parents (that is, if
                            # the block is the entrypoint).
                            if len(block.parents) == 0:
                                can_merge = False
                                break

                            block_value = None
                            for value, label in I.conds:
                                if label == block.label or self.CFG[label] in block.parents:
                                    if block_value is None:
                                        block_value = value
                                    elif block_value != value:
                                        can_merge = False
                                        break
                            if not can_merge:
                                break

                    if not can_merge:
                        continue

                    ampy.debug.print(self.ID, f"Merging {block.label} into only child {child.label}")
                    reduced = True
                    block_parents = block.parents
                    for parent in block_parents:
                        if isinstance(parent[-1], ampy.types.GotoInstruction):
                            parent.remove_child(block)
                            parent.add_child(child)
                        else: # otherwise, parent conditionally branches to block
                            cond = parent[-1].cond
                            iftrue = block.label == parent[-1].iftrue
                            parent.remove_child(block)
                            if len(parent.children) == 0:
                                parent.add_child(child)
                            else:
                                parent.add_child(child, cond=cond, new_child_if_cond=iftrue)

                    # we also need to deal with the phi nodes in child block
                    for I in child:
                        if isinstance(I, ampy.types.PhiInstruction):
                            new_conds = []
                            for val, label in I.conds:
                                if label == block.label:
                                    # expand this block into all of its parents
                                    for parent in block_parents:
                                        new_conds.append((val, parent.label))
                                elif self.CFG[label] not in block_parents:
                                    # parent blocks are already handled by
                                    # the above clause
                                    new_conds.append((val, label))
                            I.conds = tuple(new_conds)

                    if block == self.CFG.entrypoint:
                        self.CFG.set_entrypoint(child.label)
                    self.CFG.remove_block(block.label, ignore_keyerror=True)

            if not reduced:
                break
            self.CFG.tidy()
            changed = True

        if changed:
            return tuple(opt for opt in self.opts if opt.ID in ("branch-elim", "ssa"))
        return self.opts

