import ampy.types

class ParseError(Exception):

    def __init__(self, line, message):
        self.message = message
        self.line = line
        super().__init__(message)

class BadFlowError(Exception):

    def __init__(self, blocklabel, message):
        self.label = blocklabel
        self.message = message
        super().__init__(message)

class BadAddressError(Exception):

    def __init__(self, address, message):
        self.addr = address
        self.message = message
        super().__init__(message)

class BasicBlock:

    def __init__(self, addr:int, label:str, instructions:list, children=(0,), parents=set()):
        self._addr = addr # key for CFG dictionary
        self._label = label
        self._instructions = instructions
        self._children = children
        self._parents = parents
        # self._children is a tuple (N, ...) whose form is determined by N:
        # N = 0: (0, ) -> the block is an exit point
        # N = 1: (1, addr) -> block branches unconditionally to addr
        # N = 2: (2, "%cond", addr_if_true, addr_if_false)
        self._local_pc = 0 # local prorgam counter for block

    def __repr__(self):
        return (f"{self.name}\n{'':->{len(self.name)}}\n"
                + "parents: " + ", ".join(f"0x{parent:04x}" for parent in self._parents)
                + '\n' + '\n'.join(repr(instr) for instr in self))

    def __len__(self):
        return len(self._instructions)
    
    def __iter__(self):
        for instruction in self._instructions:
            yield instruction

    @property
    def addr(self):
        return self._addr

    @property
    def label(self):
        return self._label

    @property
    def name(self):
        return f"Block<0x{self._addr:04x}> ({self._label})"

    @property
    def completed(self):
        return self._local_pc >= len(self)

    @property
    def children(self):
        if self._children[0] == 0:
            return ()
        if self._children[0] == 1:
            return (self._children[1],)
        return (self._children[2], self._children[3])
    
    @property
    def parents(self):
        return tuple(sorted(self._parents))

    def add_parent(self, parent):
        self._parents.add(parent)
    
    def remove_parent(self, parent):
        if parent not in self._parents:
            raise ValueError(f"{self.name} does not have a parent at 0x{parent:04x}")

    def add_child(self, child, label, cond=None, new_child_if_cond=False):
        if self._children[0] == 0:
            if cond is not None:
                raise BadFlowError(self.label, f"Added branch condition {cond} to unconditional branch out of {self.name}")
            self._children = (1, child)
            # block was originally an exit node, so add goto instruction
            self._instructions.append(ampy.types.GotoInstruction(label))
        elif self._children[0] == 1:
            if cond is None:
                raise BadFlowError(self.label, f"Condition necessary for conditional branch out of {self.name}")
            oldchild = self._children[1]
            # block ended with a goto
            oldlabel = self._instructions[-1].target
            if new_child_if_cond:
                self._children = (2, cond, child, oldchild)
                self._instructions[-1] = ampy.types.BranchInstruction(cond, label, oldlabel)
            else:
                self._children = (2, cond, oldchild, child)
                self._instructions[-1] = ampy.types.BranchInstruction(cond, oldlabel, label)
        else:
            raise BadFlowError(f"Adding target to conditional branch out of {self.name}")

    def remove_child(self, child):
        if child not in self.children:
            raise ValueError(f"{self.name} does not branch to 0x{child:04x}")
        if self._children[0] == 1:
            self._children = (0,)
            self._instructions.pop() # no more branch
        else: # self._children[0] == 2
            if self._children[2] == child:
                self._children = (1, self._children[3])
                label = self._instructions[-1].iffalse
            else:
                self._children = (1, self._children[2])
                label = self._instructions[-1].iftrue
            self._instructions[-1] = ampy.types.GotoInstruction(label)

    def step(self, vardict, verbose):
        if self.completed:
            raise Exception(f"Attempting to step through execution of exhausted block")
        instruction = self._instructions[self._local_pc]
        verbose(f"[0x{self._addr + self._local_pc:04x}]", repr(instruction))
        errno = instruction(vardict)
        self._local_pc += 1
        if errno:
            verbose(f"\t\033[31mnonzero exit code {errno}\033[m")
        return errno

    def run(self, vardict, verbose):
        while not self.completed:
            self.step(vardict, verbose)

    def reset(self):
        self._local_pc = 0


class CFG:

    def __init__(self, state={}):
        self._blocks = dict() # int(addr) : BasicBlock dict
        self._pc = 0
        self._current_block = None # leave None if not fetched
        self._reset_state = state
        self._vd = ampy.types.VarDict(state=state)
        self._addr = 0
        self._exited = False

    def __iter__(self):
        for addr in sorted(self._blocks):
            yield self._blocks[addr]

    def __len__(self):
        return len(self._blocks)
    
    def __repr__(self):
        return f"Control Flow Graph:\n{repr(self._vd)}\n" + "\n\n".join(repr(self._blocks[addr]) for addr in sorted(self._blocks))

    def __getitem__(self, var):
        if var in self._vd:
            return self._vd[var]
        else:
            raise KeyError(f"{var} not a defined variable in current state")

    @property
    def vars(self):
        return self._vd.vars
    @property
    def exited(self):
        return self._exited

    @property
    def pc(self):
        if self._current_block is None:
            return self._pc
        else:
            return self._pc + self._current_block._local_pc
    
    def add_block(self, label:str, instructions:list, children=(0,)):
        """
        NB: add block method does not notify parents of new children or children of new parents

        Assumes first block is the entry point
        """
        if not label.startswith('@'):
            raise ValueError("Labels must begin with '@'")
        if label in self._vd:
            raise KeyError(f"Cannot reassign label {label} (already set to 0x{self._vd[label]:04x})")
        addr = self._addr
        self._addr += len(instructions) # just to be cute, I guess
        self._vd[label] = addr
        self._vd[label] = addr
        self._blocks[addr] = BasicBlock(addr, label, instructions, children=children, parents=set())
        return self._blocks[addr]
    
    def remove_block(self, addr=None, label=None):
        if addr is None:
            if label is None:
                raise ValueError("Did not specify which block to remove.")
            addr = self._vd[label]

        if label is None:
            # addr is not None
            if addr not in self._blocks:
                raise ValueError("Attempting to remove block at invalid address 0x{addr}")
            for l in self._vd:
                if self._vd[l] == addr:
                    label = l
                    break
        
        # at this point, self._vd[label] = addr
        block = self._blocks[addr]
        for child in block.children:
            self._blocks[child].remove_parent(addr)
        for parent in block.parents:
            self._blocks[parent].remove_child(addr)

        del self._blocks[addr]
        del self._vd[label]

    def verify_completeness(self):
        """
        Call after all basic blocks have been added to CFG
        """
        for addr in self._blocks:
            block = self._blocks[addr]
            for child in block.children:
                if child not in self._blocks:
                    raise BadAddressError(child, f"{block.name} points to invalid address 0x{child:04x}")
                self._blocks[child].add_parent(addr)

        for addr in self._blocks:
            block = self._blocks[addr]
            for parent in block.parents:
                if parent not in self._blocks:
                    raise BadAddressError(parent, f"{block.name} claims to be a target for block at invalid address 0x{parent:04x}")
                pblock = self._blocks[parent]
                if addr not in pblock.children:
                    raise FlowError(f"{block.name} is not a target for {pblock.name}")

    def _fetch_block(self):
        if self._current_block is None:
            if self._pc not in self._blocks:
                raise BadAddressError(self._pc, f"Fetching block at invalid address 0x{self._pc:04x}")
            self._current_block = self._blocks[self._pc]
            self._current_block.reset() # reset local program counter
        return self._current_block

    def _jump(self):
        if not self._vd.jumped:
            raise Exception("Unauthorised jump")
        self._vd.jumped = False
        self._pc = self._vd["#pc"]
        self._current_block = None # invalidate current block

    def step(self, verbose):
        if self.exited:
            raise Exception("Attempting to execute after exiting")
        block = self._fetch_block()
        block.step(self._vd, verbose)
        if self._vd.jumped:
            self._jump()
        elif block.completed:
            self._exited = True

    def run_block(self, verbose):
        if self._exited:
            raise Exception("Attempting to execute after exiting")
        block = self._fetch_block()
        block.run(self._vd, verbose)
        if self._vd.jumped:
            self._jump()
        elif block.completed:
            self._exited = True

    def run(self, verbose):
        while not self.exited:
            self.run_block(verbose)

    def reset(self, state=None):
        self._pc = 0
        self._current_block = None
        if state is None:
            state = self._reset_state
        self._vd = ampy.types.VarDict(state=state)
        self._exited = False

class CFGBuilder:

    def _commit_block(self, cfg, fallthrough=False, children=(0,)):
        if self._current_block is None:
            return
        if self._block_label is None:
            self._block_label = f"@._{self._anon}"
            self._anon += 1
        block = cfg.add_block(self._block_label, instructions=self._current_block, children=children)
        if self._fallthrough_parent is not None:
            self._fallthrough_parent.add_child(block.addr, block.label)
            self._fallthrough_parent = None
        if fallthrough:
            self._fallthrough_parent = block
        self._current_block = None
        self._block_label = None

    def build_cfg(self, instructions, initial_state=ampy.types.VarDict()):
        cfg = CFG(state=initial_state)
        self._current_block = None
        self._block_label = None
        self._fallthrough_parent = None
        self._anon = 0 # counter for anonymous block labels

        for (i, instruction_str) in enumerate(instructions):
            if ';' in instruction_str:
                instruction_str, _ = instruction_str.split(';', 1)
            if instruction_str.startswith('@') and ':' in instruction_str:
                # possible fallthrough
                self._commit_block(cfg, fallthrough=True)
                self._block_label, instruction_str = instruction_str.split(':', 1)
                self._current_block = []

            instruction_str = instruction_str.strip()
            if len(instruction_str) == 0:
                continue
            instruction = None
            for op in ampy.types.opcodes:
                instruction = ampy.types.opcodes[op].read(instruction_str)
                if instruction is not None:
                    break
            if instruction is None:
                raise ParseError(i, f"Cannot parse instruction \"{instruction_str}\"")
            if self._current_block is None:
                self._current_block = []
            self._current_block.append(instruction)
            if isinstance(instruction, ampy.types.BranchInstructionClass):
                self._commit_block(cfg)

        self._commit_block(cfg)
        
        cfg.verify_completeness()
        return cfg

