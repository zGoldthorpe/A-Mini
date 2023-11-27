"""
Simple fuzzer
===============
Goldthorpe
"""

import random

import utils.debug
import utils.printing

from ui.errors import perror, die, unexpected

import ampy.types as amt

class FuzzUI:
    """
    A-Mi fuzzer: generates a program

    The fuzzer builds the CFG in several stages, where each stage
    is sampled from templates.
    """

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument("--var",
                        type=float,
                        dest="FUIvar",
                        metavar="FLOAT",
                        default=0.1,
                        help="The probability of generating new variables per block (default: 0.1).")
        parser.add_argument("--recycle",
                        type=float,
                        dest="FUIrecycle",
                        metavar="FLOAT",
                        default=0.1,
                        help="The probability of redefining existing variables per block (default: 0.1).")
        parser.add_argument("--intmax",
                        type=int,
                        dest="FUImax",
                        metavar="MAX",
                        default=64,
                        help="Sample integers from [-MAX, MAX]. NB: this is also used for loop ranges.")
        parser.add_argument("--stage-weights",
                        nargs=3,
                        dest="FUIweights",
                        metavar="W",
                        help=("Weight vector of floats for [CHAIN, BRANCH, LOOP] stage constructors."
                            " Larger values cause those stages to occur more often; larger magnitude grows code size"
                            " (default: 10. 20. 10.)."))

    @classmethod
    def arg_init(cls, parsed_args):
        return cls(var=parsed_args.FUIvar,
                recycle=parsed_args.FUIrecycle,
                intmax=parsed_args.FUImax,
                weights=parsed_args.FUIweights)

    def __init__(self, var=0.1, recycle=0.1, intmax=64, weights=None):
        self._newvar = var
        self._recycle = recycle
        self._maxconst = intmax
        if weights is None:
            weights = [10., 20., 10.]
        self._weights = weights

    def generate(self):
        """
        Generate a CFG
        """
        self._cfg = amt.CFG()
        self._block = 0
        self._var = 0
        entrypoint = self.newblock()
        self._cfg.set_entrypoint(entrypoint.label)
        self.stage(entrypoint, [], [])
        return self._cfg

    def stage(self, block, varlist, recycle):
        """
        Construct a new stage at the given block, assuming block is an endpoint.
        Returns endpoint of stage
        """
        # first, introduce some new variables
        while (random.random() < (len(varlist)+1)**(-self._newvar)):
            instr = self.create_new_def(varlist, recycle)
            def isdigit(arg):
                try:
                    int(arg)
                    return True
                except ValueError:
                    return False

            if isinstance(instr, (amt.DivInstruction, amt.ModInstruction)) and (not isdigit(instr.operands[1]) or instr.operands[1] == '0'):
                # create a guard from division by zero
                cond = self.newvar()
                block.insert(-1, amt.NeqInstruction(cond, instr.operands[1], '0'))
                safe = self.newblock()
                unsafe = self.newblock()
                block.add_child(unsafe)
                block.add_child(safe, cond=cond, new_child_if_cond=True)
                safe.insert(-1, instr)
                unsafe.insert(-1, amt.MovInstruction(instr.target, '0'))
                # rejoin after guard and continue as though nothing happened
                block = self.newblock()
                safe.add_child(block)
                unsafe.add_child(block)
            elif isinstance(instr, (amt.LShiftInstruction, amt.RShiftInstruction)) and not isdigit(instr.operands[1]):
                # since shifting is exponential, we need a guard from shifting too much
                block.insert(-1, amt.ModInstruction(instr.operands[1], instr.operands[1], str(random.choice([-1,1])*self._maxconst)))
                block.insert(-1, instr)
            else:
                block.insert(-1, instr)

            varlist.append(instr.target)
            if random.random() < self._recycle:
                recycle.append(instr.target)

        # now, decide on a stage
        block = self.weighted_choice([
                    (self.exit_stage, len(self._cfg)),
                    (self.chain_stage, self._weights[0]),
                    (self.if_stage, self._weights[1]),
                    (self.loop_stage, self._weights[2]),
                    ])(block, varlist, recycle)

        # finally, probe some of the variables
        mask = random.randrange(0, 1<<len(varlist)) * (random.random() > len(self._cfg)**-0.3)
        for i in range(len(varlist)):
            if (mask & (1 << i)) and random.random() < 0.1:
                block.insert(-1, amt.WriteInstruction(varlist[i]))

        return block

    def exit_stage(self, block, varlist, recycle):
        """
        Nop
        """
        return block

    def chain_stage(self, block, varlist, recycle):
        """
        Chains current block to another via an unconditional branch
        """
        chain = self.newblock()
        block.add_child(chain)
        return self.stage(chain, varlist, recycle)
    
    def if_stage(self, block, varlist, recycle):
        """
        Branch and join
        """
        left = self.newblock()
        right = self.newblock()
        cond = self.newvar()
        IC = self.weighted_choice([
                    (amt.EqInstruction, 1),
                    (amt.NeqInstruction, 1),
                    (amt.LeqInstruction, 10),
                    (amt.LtInstruction, 10)])
        block.insert(-1, IC(cond, self.choose_operand(varlist), self.choose_operand(varlist)))
        block.add_child(left)
        block.add_child(right, cond=cond)

        # now let both have at it
        left = self.stage(left, list(varlist), list(recycle))
        right = self.stage(right, list(varlist), list(recycle))

        join = self.newblock()
        left.add_child(join)
        right.add_child(join)
        return self.stage(join, varlist, recycle)

    def loop_stage(self, block, varlist, recycle):
        """
        Implements a "for(i = L; i < R; ++i)" kind of loop
        """
        start = random.randint(-10, 10)
        end = random.randint(-10, 10)
        var = self.newvar()

        if start < end:
            step = random.randint(1, 5)
            lhs = str(end)
            rhs = var
        else:
            step = -random.randint(1, 5)
            lhs = var
            rhs = str(end)

        block.insert(-1, amt.MovInstruction(var, str(start)))
        loop = self.newblock()
        block.add_child(loop)

        endloop = self.stage(loop, varlist, recycle) # do not add the iteration variable, to ensure loop terminates

        cond = self.newvar()
        endloop.insert(-1, amt.AddInstruction(var, var, str(step)))
        endloop.insert(-1, random.choice([amt.LeqInstruction, amt.LtInstruction])(cond, lhs, rhs))

        exitblock = self.newblock()

        endloop.add_child(loop)
        endloop.add_child(exitblock, cond=cond, new_child_if_cond=True)

        varlist.append(var) # when the loop is completed, the variable is free for use or reuse
        if random.random() < self._recycle:
            recycle.append(var)

        return self.stage(exitblock, varlist, recycle)



    def create_new_def(self, varlist, recycle):
        if len(recycle) > 0 and random.random() > 1 / len(recycle):
            target = random.choice(list(recycle))
        else:
            target = self.newvar()
        if len(varlist) == 0:
            IC = amt.ReadInstruction
        else:
            IC = self.weighted_choice([
                    (amt.ReadInstruction, 1),
                    (amt.MovInstruction, 1),
                    (amt.AddInstruction, 5),
                    (amt.SubInstruction, 5),
                    (amt.NegInstruction, 1),
                    (amt.MulInstruction, 4),
                    (amt.DivInstruction, 1),
                    (amt.ModInstruction, 2),
                    (amt.AndInstruction, 3),
                    (amt.OrInstruction,  3),
                    (amt.XOrInstruction, 3),
                    (amt.LShiftInstruction, 3),
                    (amt.RShiftInstruction, 2),
                    (amt.EqInstruction, 1),
                    (amt.NeqInstruction, 1),
                    (amt.LtInstruction, 1),
                    (amt.LeqInstruction, 1)])
        
        if issubclass(IC, amt.BinaryInstructionClass):
            nargs = 2
        elif IC == amt.ReadInstruction:
            nargs = 0
        else:
            nargs = 1
        
        operands = []
        for _ in range(nargs):
            operands.append(self.choose_operand(varlist))
        return IC(target, *operands)

    def choose_operand(self, varlist):
        if len(varlist) == 0 or random.random() < len(varlist)**-.2:
            return str(self.newint())
        return random.choice(varlist)


    @classmethod
    def weighted_choice(cls, choices):
        """
        Expects a list of (choice, weight) pairs.
        """
        accum = []
        tot = 0.
        for choice, weight in choices:
            tot += weight
            accum.append((choice, tot))
        chx = random.random()*tot
        i = 0
        while accum[i][1] < chx:
            i += 1
        return accum[i][0]

    def newint(self):
        return random.randint(-self._maxconst, self._maxconst)

    def newvar(self):
        var = f"%{self._var}"
        self._var += 1
        return var

    def newblock(self):
        label = f"@{self._block}"
        self._block += 1
        self._cfg.create_block(label)
        return self._cfg[label]


class FuzzWriter:
    """
    Class for producing random inputs on-demand, and records to a file
    """

    def __init__(self, fname, intmin, intmax):
        self._fname = fname
        self._min = intmin
        self._max = intmax
        with open(self._fname, 'w') as f:
            f.write('')

    def __str__(self):
        return self._fname

    def readline(self):
        # program is querying an input
        # generate and record result
        out = random.randint(self._min, self._max)
        res = f"{out}\n"
        with open(self._fname, 'a') as f:
            f.write(res)
        return res

    def close(self):
        pass


