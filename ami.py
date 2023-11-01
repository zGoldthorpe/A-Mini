"""
Assembly-Minimal
==================
Goldthorpe

This is a proof-of-concept interpreter for A-Mi
"""

import argparse
import os
import re
import sys

import ampy.interpret as ami
import ampy.printing  as amp
import ampy.reader    as amr
import ampy.types     as amt

### command-line argument handling ###

argparser = argparse.ArgumentParser(
                description="Proof-of-concept interpreter for A-Mi")

argparser.add_argument("fname",
            metavar="<prog.ami>",
            nargs="?",
            help="""File containing plaintext A-Mi instructions.
                    If omitted, code will be read through STDIN.""")
argparser.add_argument("-e", "--entrypoint",
            dest="entrypoint",
            action="store",
            type=str,
            help="Specify the entrypoint label")
argparser.add_argument("-A", "--ban-anonymous-blocks",
            dest="anon_blocks",
            action="store_false",
            help="Assert that all basic blocks in code must be explicitly labelled.")
argparser.add_argument("-i", "--prompt",
            dest="prompt",
            action="store_true",
            help="Enable prompt messages when A-Mi code calls a 'read' or a 'write'.")
argparser.add_argument("-t", "--trace",
            dest="trace",
            action="store_true",
            help="Output execution trace to STDERR")
argparser.add_argument("-B", "--suppress-breakpoint",
            dest="brkpt",
            action="store_false",
            help="Ignore breakpoints in code")
argparser.add_argument("--plain",
            dest="format",
            action="store_false",
            help="Print output in plaintext (without ANSI colouring)")
argparser.add_argument("--interrupt",
            dest="step",
            choices=("never", "instructions", "blocks"),
            const="blocks",
            default="never",
            nargs="?",
            help="Insert breakpoint at specified frequency (default: never)")

args = argparser.parse_args()

amp.Printing.can_format &= args.format

if args.entrypoint is not None and not args.entrypoint.startswith('@'):
    args.entrypoint = f"@{args.entrypoint}"

### get source code ###

if args.fname is not None:
    if not os.path.exists(args.fname):
        amp.perror(f"Source file {args.fname} does not exist.", file=sys.stderr)
        exit(-1)
    if not os.path.isfile(args.fname):
        amp.perror(f"{args.fname} does not point to a file!", file=sys.stderr)
        exit(-2)
    with open(args.fname) as file:
        instructions = file.readlines()
else:
    args.fname = "@"
    amp.pprompt(amp.tame_whitespace("""
        Enter A-Mi instructions below.
        Press Ctrl-D to end input, and Ctrl-C to cancel."""))
    instructions = []
    while True:
        amp.pprompt(f"{len(instructions)+1: >4d} | ", end='', flush=True)
        try:
            instructions.append(input())
        except KeyboardInterrupt:
            # ^C
            print()
            exit()
        except EOFError:
            # ^D
            print()
            break

### parse source ###

builder = amr.CFGBuilder(allow_anon_blocks=args.anon_blocks,
                         entrypoint_label=args.entrypoint)
try:
    cfg = builder.build(*instructions)
except amr.EmptyCFGError:
    amp.perror("Program is empty!", file=sys.stderr)
    exit(-3)
except amr.NoEntryPointError as e:
    amp.perror(e.message, file=sys.stderr)
    exit(-4)
except amr.AnonymousBlockError as e:
    amp.perror(f"{args.fname}::{e.line+1}:", instructions[e.line], file=sys.stderr)
    amp.perror("All basic blocks must be explicitly labelled.", file=sys.stderr)
    exit(-5)
except amr.ParseError as e:
    amp.perror(f"{args.fname}::{e.line+1}:", instructions[e.line], file=sys.stderr)
    amp.perror(e.message, file=sys.stderr)
    exit(-6)

### run program ###

interpreter = ami.Interpreter()
interpreter.load(cfg)
qhist = dict() # tracker for old breakpoint queries

while interpreter.is_executing:
    I = interpreter.current_instruction
    brkpt = None
    if args.trace:
        amp.psubtle(repr(I), file=sys.stderr)

    try:
        interpreter.run_step()
    except KeyboardInterrupt:
        print()
        exit()
    except KeyError as e:
        amp.perror("Undefined register:", e, file=sys.stderr)
        exit(-7)
    except ami.ReadInterrupt as e:
        val = None
        while True:
            if args.prompt:
                amp.pprompt(e.register, "= ", end='', flush=True)
            try:
                val = int(input())
                break
            except ValueError:
                amp.perror("Please enter a single decimal integer.", file=sys.stderr)
                val = None
            except KeyboardInterrupt:
                print()
                exit()
            except Exception as e:
                amp.perror(f"Unexpected {type(e).__name__}: {e}", file=sys.stderr)
                exit(-8)
        interpreter.write(e.register, val)
    except ami.WriteInterrupt as e:
        try:
            val = interpreter.read(e.register)
        except KeyError as e:
            amp.perror(e.message)
            exit(-9)
        if args.prompt:
            amp.pprompt(e.register, "= ", end='')
        print(val)
    except ami.BreakpointInterrupt as e:
        brkpt = e.name

    if brkpt is None:
        if (args.step == "instructions"
                or (args.step == "blocks" and isinstance(I, amt.BranchInstructionClass))):
            brkpt = f"<{repr(I)}>"

    if args.brkpt and brkpt is not None:
        amp.pdebug(f"Reached breakpoint {brkpt}")

        while True:
            amp.pdebug("(ami-db) ", end='', flush=True)
            try:
                q = input().lower().strip()
            except:
                exit(0)
            if len(q) == 0:
                break

            if q.startswith('h'):
                amp.pdebug("Press <enter> to resume execution.")
                amp.pdebug("Enter a space-separated list of register names or regex patterns to query register values.")
                amp.pdebug("Enter \"exit\" to terminate execution and quit.")
            if q == "exit":
                exit(0)

            queries = set()
            for qre in q.split():
                try:
                    pat = re.compile(qre)
                except Exception as ce:
                    amp.perror(f"Cannot parse expression {qre}: {ce}")
                    continue
                for reg in interpreter.registers:
                    if pat.fullmatch(reg):
                        queries.add(reg)

            if len(queries) == 0:
                amp.perror("No registers match query patterns")
                continue

            maxllen = max(len(reg) for reg in queries)
            maxrlen = max(len(str(interpreter.read(reg))) for reg in queries)

            response = dict()
            for reg in queries:
                val = interpreter.read(reg)
                response[reg] = f"{val: >{maxrlen}}"
                if reg not in qhist:
                    response[reg] += " (new)"
                    qhist[reg] = val
                elif val != qhist[reg]:
                    response[reg] += f" (changed from {qhist[reg]})"
                    qhist[reg] = val

            for reg in sorted(queries):
                amp.pprompt(f"{reg: >{maxllen}} = {response[reg]}")
