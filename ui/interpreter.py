"""
Interpreter
=============
Goldthorpe
"""

import re
import sys

import ampy.interpret
import ampy.printing
import ampy.types

from ui.errors import perror, die, unexpected

class InterpreterUI:

    @classmethod
    def add_arguments(cls, parser):

        parser.add_argument("-i", "--prompt",
                dest="IUIprompt",
                action="store_true",
                help="Enable prompt messages when A-Mi code calls a 'read' or a 'write'.")
        parser.add_argument("-t", "--trace",
                dest="IUItrace",
                action="store_true",
                help="Output execution trace to STDERR")
        parser.add_argument("-B", "--suppress-breakpoint",
                dest="IUIbrkpts",
                action="store_false",
                help="Ignore breakpoints in code")
        parser.add_argument("--interrupt",
                dest="IUIinterrupt",
                choices=("never", "instructions", "blocks"),
                const="blocks",
                default="never",
                nargs="?",
                help="Insert breakpoint at specified frequency (default: never)")

    def __init__(self, parsed_args):
        self._interpreter = ampy.interpret.Interpreter()

        self.trace = parsed_args.IUItrace
        self.prompt = parsed_args.IUIprompt
        self.interrupt = parsed_args.IUIinterrupt
        self.brkpts = parsed_args.IUIbrkpts

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
                    self.debug(e.name)
            
            if not self.brkpts or self.interrupt == "never" or isinstance(I, ampy.types.BrkInstruction):
                continue
            if self.interrupt == "instructions" or isinstance(I, ampy.types.BranchInstructionClass):
                self.debug(f"<{repr(I)}>")

    def read_int(self, reg):
        val = None
        while True:
            if self.prompt:
                ampy.printing.pprompt(reg, '=', end=' ', flush=True)

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
                perror("Unexpected EOF.")
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
            ampy.printing.pprompt(reg, "= ", end='')

        print(val)

    def debug(self, brkpt):
        """
        Open debug interface during breakpoint
        """
        ampy.printing.pprompt("Reached breakpoint", brkpt)
        while True:
            ampy.printing.pprompt(f"(ami-db)", end=' ', flush=True)
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
                return

            if q.startswith('h'):
                ampy.printing.pquery("Press <enter> to resume execution.")
                ampy.printing.pquery("Enter a space-separated list of register names or regex patterns to query register values.")
                ampy.printing.pquery("Enter \"exit\" to terminate execution and quit.")
            if q == "exit":
                exit()

            queries = set()
            for qre in q.split():
                try:
                    pat = re.compile(qre)
                except re.error as se:
                    ampy.printing.perror(f"Cannot parse expression {qre}: {se}")
                    continue
                except Exception as e:
                    unexpected(e)

                for reg in self._interpreter.registers:
                    if pat.fullmatch(reg):
                        queries.add(reg)

            if len(queries) == 0:
                ampy.printing.perror("No registers match query patterns")
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
                ampy.printing.pquery(f"{reg: >{maxllen}} = {response[reg]}")


    def update_trace(self, I):
        if self._interpreter.block_label != self._label:
            self._label = self._interpreter.block_label
            self.subtle_parallel(f"{self._label}:", f"{self._label}:")
        trI = self._substitute_uses(I)
        self.subtle_parallel(repr(I), repr(trI))

    def subtle_parallel(self, left, right):
        ampy.printing.psubtle(f"{left: <{self.trace_width}}", '|', right, file=sys.stderr)

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
            return ampy.types.PhiInstruction(I.target, *filter(lambda t: t[1] == self._interpreter._prev_label, I.conds))
        if isinstance(I, ampy.types.BranchInstruction):
            return ampy.types.BranchInstruction(sub(I.cond), I.iftrue, I.iffalse)
        if isinstance(I, ampy.types.WriteInstruction):
            return ampy.types.WriteInstruction(sub(I.operand))
        
        return I

