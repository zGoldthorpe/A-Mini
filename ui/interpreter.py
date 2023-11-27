"""
Interpreter
=============
Goldthorpe
"""

import re
import sys
import time

import utils.debug
import utils.printing

from ui.errors import perror, die, unexpected

import ampy.interpret
import ampy.types


class InterpreterUI:

    @classmethod
    def add_arguments(cls, parser):

        parser.add_argument("-i", "--integer",
                dest="IUIbits",
                type=int,
                default=128,
                help="Specify the number of bits per register (default: 128). Use 0 for infinite bits.")
        parser.add_argument("-t", "--trace",
                dest="IUItrace",
                action="store_true",
                help="Output execution trace to STDERR")
        parser.add_argument("-B", "--suppress-breakpoint",
                dest="IUIbrkpts",
                action="store_false",
                help="Ignore breakpoints in code")
        parser.add_argument("--prompt",
                dest="IUIprompt",
                action="store_true",
                help="Enable prompt messages when A-Mi code calls a 'read' or a 'write'.")
        parser.add_argument("--interrupt",
                dest="IUIinterrupt",
                choices=("never", "instructions", "blocks"),
                const="blocks",
                default="never",
                nargs="?",
                help="Insert breakpoint at specified frequency (default: never)")

    @classmethod
    def arg_init(cls, parsed_args):
        return cls(bits=parsed_args.IUIbits,
                trace=parsed_args.IUItrace,
                prompt=parsed_args.IUIprompt,
                interrupt=parsed_args.IUIinterrupt,
                brkpts=parsed_args.IUIbrkpts)

    def __init__(self, bits=128, trace=False, prompt=False, interrupt="never", brkpts=True):
        self._interpreter = ampy.interpret.Interpreter(bits)
        
        self.trace = trace
        self.prompt = prompt
        self.interrupt = interrupt
        self.brkpts = brkpts

        # formatting for trace output
        self._trace_width = None
        # query history tracker for breakpoints
        self._qhist = {}
        # tracker of current label
        self._label = None

    def load_cfg(self, cfg):
        """
        Load the CFG of the program to run.
        """
        self._cfg = cfg
        self._interpreter.load(self._cfg)

    def run(self):
        runtime = time.process_time()
        while self._interpreter.is_executing:
            I = self._interpreter.current_instruction
            if self.trace:
                self.update_trace(I)

            try:
                self._interpreter.run_step()
            except KeyboardInterrupt:
                print()
                exit()
            except KeyError as e:
                die(f"Undefined register: {e}")
            except ampy.interpret.ReadInterrupt as e:
                self.read_int(e.register)
            except ampy.interpret.WriteInterrupt as e:
                self.write(e.register)
            except ampy.interpret.BreakpointInterrupt as e:
                if self.brkpts:
                    self.debugger(e.name)
            except ampy.interpret.UnknownInstructionError as e:
                die(f"Unknown instruction at {e.block.label}:{e.instruction_index}:\n\t{e.message}")
            except ampy.interpret.InstructionException as e:
                die(f"An exception occurred at {e.block.label}:{e.instruction_index}:\n\t{e.message}")
            
            if not self.brkpts or self.interrupt == "never" or isinstance(I, ampy.types.BrkInstruction):
                continue
            if self.interrupt == "instructions" or isinstance(I, ampy.types.BranchInstructionClass):
                self.debugger(f"<{repr(I)}>")

        # execution completed
        runtime = time.process_time() - runtime
        utils.debug.print("interpreter", "total execution time:", f"{runtime:.3f}s")

    def read_int(self, reg):
        val = None
        while True:
            if self.prompt:
                utils.printing.pprompt(reg, '=', end=' ', flush=True)

            try:
                val = int(input())
                break
            except ValueError:
                perror("Please enter a single decimal integer.")
                val = None
            except KeyboardInterrupt:
                print()
                exit()
            except EOFError:
                die("Unexpected EOF.")
            except Exception as e:
                unexpected(e)
        self._interpreter.write(reg, val)

    def write(self, reg):
        try:
            val = self._interpreter.read(reg)
        except KeyError as e:
            die(e.message)
        except Exception as e:
            unexpected(e)

        if self.prompt:
            utils.printing.pprompt(reg, "= ", end='')

        print(val)

    def debugger(self, brkpt):
        """
        Open debug interface during breakpoint
        """
        utils.printing.pprompt("Reached breakpoint", brkpt)
        showprompt = True
        while True:

            if showprompt:
                utils.printing.pquery("Enter a space-separated list of register names or regex patterns to query register values.")
                utils.printing.pquery("Enter nothing to exit debugger and resume execution.")
                utils.printing.pquery("Enter \"h\" to print this help message again.")
                utils.printing.pquery("Enter \"exit\" to terminate execution and quit.")
                showprompt = False

            utils.printing.pprompt(f"(ami-db)", end=' ', flush=True)
            try:
                q = input().lower().strip()
            except KeyboardInterrupt:
                print()
                exit()
            except EOFError:
                q = ""
            except Exception as e:
                unexpected(e)

            if len(q) == 0:
                utils.printing.pquery("Resuming program execution.")
                return

            if q.startswith('h'):
                showprompt = True
                continue
            if q == "exit":
                utils.printing.pquery("Exiting program.")
                exit()

            queries = set()
            for qre in q.split():
                try:
                    pat = re.compile(qre)
                except re.error as se:
                    utils.printing.perror(f"Cannot parse expression {qre}: {se}")
                    continue
                except Exception as e:
                    unexpected(e)

                for reg in self._interpreter.registers:
                    if pat.fullmatch(reg):
                        queries.add(reg)

            if len(queries) == 0:
                utils.printing.perror("No registers match query patterns")
                continue

            maxllen = max(len(reg) for reg in queries)
            maxrlen = max(len(str(self._interpreter.read(reg))) for reg in queries)

            response = dict()
            for reg in queries:
                val = self._interpreter.read(reg)
                response[reg] = f"{val: >{maxrlen}}"
                if reg not in self._qhist:
                    response[reg] += " (new)"
                    self._qhist[reg] = val
                elif val != self._qhist[reg]:
                    response[reg] += f" (changed from {qhist[reg]})"
                    self._qhist[reg] = val

            for reg in sorted(queries):
                utils.printing.pquery(f"{reg: >{maxllen}} = {response[reg]}")


    def update_trace(self, I):
        if self._interpreter.block_label != self._label:
            self._label = self._interpreter.block_label
            self.subtle_parallel(f"{self._label}:", f"{self._label}:")
        trI = self._substitute_uses(I)
        self.subtle_parallel(repr(I), repr(trI))

    def subtle_parallel(self, left, right):
        utils.printing.psubtle(f"{left: <{self.trace_width}}", '|', right, file=sys.stderr)

    @property
    def trace_width(self):
        if self._trace_width is None:
            self._trace_width = max(
                    max(len(repr(I)) for I in block)
                    for block in self._cfg)
        return self._trace_width

    def _substitute_uses(self, I):
        """
        Substitute arguments of instruction by
        their interpretations, where possible.
        """
        def sub(var):
            try:
                return str(self._interpreter.read(var))
            except KeyError:
                return var
            except Exception as e:
                unexpected(e)

        if isinstance(I, ampy.types.BinaryInstructionClass):
            return type(I)(I.target, *map(sub, I.operands))
        if isinstance(I, ampy.types.MovInstruction):
            return ampy.types.MovInstruction(I.target, sub(I.operand))
        if isinstance(I, ampy.types.PhiInstruction):
            return ampy.types.PhiInstruction(I.target,
                    *map(lambda t: (sub(t[0]), t[1]), 
                        filter(lambda t: t[1] == self._interpreter._prev_label, I.conds)))
        if isinstance(I, ampy.types.BranchInstruction):
            return ampy.types.BranchInstruction(sub(I.cond), I.iftrue, I.iffalse)
        if isinstance(I, ampy.types.WriteInstruction):
            return ampy.types.WriteInstruction(sub(I.operand))
        
        return I

