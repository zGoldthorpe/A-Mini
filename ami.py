"""
Proof of concept interpreter for AMini
"""

import argparse
import os
import sys

import ampy.parser as amp

parser = argparse.ArgumentParser(
        prog="A/M-i",
        description="Proof of concept A/Mini interpreter")

parser.add_argument("fname",
        metavar="<prog.ami>",
        help="file containing A/Mini instructions")
parser.add_argument("-t", "--trace",
        dest="trace",
        action="store_true",
        help="Output runtime information during execution")
parser.add_argument("-i", "--interrupt",
        dest="step",
        choices=("never", "instructions", "blocks"),
        const="blocks",
        default="never",
        nargs="?",
        help="Interrupt execution at every instruction or block and query state")
parser.add_argument("--unformatted",
        dest="formatted",
        action="store_false",
        help="Unformat output")

def pformatted(at_begin, at_end, *args, file=sys.stdout, flush=True, **kwargs):
    global formatted
    if formatted:
        print(at_begin, end='', file=file)
    print(*args, file=file, flush=flush, **kwargs)
    if formatted:
        print(at_end, end='', file=file, flush=flush)

def psubtle(*args, **kwargs):
    pformatted("\033[33m", "\033[m", *args, **kwargs)
def pprompt(*args, **kwargs):
    pformatted("\033[34m", "\033[m", *args, **kwargs)
def perror(*args, **kwargs):
    pformatted("\033[31m", "\033[m", *args, **kwargs)
def pnop(*args, **kwargs):
    pass

### Run interpreter ###

args = parser.parse_args()

fname = args.fname
formatted = args.formatted
if not os.path.exists(fname):
    perror(f"Source file {fname} does not exist")
    exit(1)
if not os.path.isfile(fname):
    perror(f"{fname} does not point to a file")
    exit(2)

with open(fname) as file:
    instructions = file.readlines()

output = psubtle if args.trace else pnop

try:
    cfg = amp.CFGBuilder().build_cfg(instructions)
except amp.ParseError as pe:
    perror(f"""Failed to parse instruction in line {pe.line+1}:
[{fname}:{pe.line+1}]\t{instructions[pe.line].strip()}""")
    exit(10)
except amp.BadAddressError as ba:
    perror(f"""An error occurred while verifying program consistency:
[{fname}] {ba.message}""")
    exit(11)
except amp.BadFlowError as fe:
    perror(f"""A build error has occurred:
[{fname}] {fe.message}""")


qhist = dict() # remember past queries to note changes
while not cfg.exited:
    if args.step == "never":
        cfg.run(verbose=output)
        exit(0)
    if args.step == "instructions":
        cfg.step(verbose=output)
    else: # args.step == "blocks"
        cfg.run_block(verbose=output)
    # now to interface
    while True:
        pprompt(f"0x{cfg.pc:04x}>> ", end='', flush=True)
        try:
            q = input()
        except:
            exit(0)
        if q.lower().startswith('h'):
            pprompt("Press <enter> to continue, or enter virtual register names to query.",
                    "Alternatively, enter \"all\" to query all virtual registers.",
                    "Or, enter \"exit\" to quit execution.", sep='\n')
            continue
        if q.lower() == "exit":
            exit(0)
        if q.lower() == "all":
            q = ' '.join(cfg.vars)
        queries = q.split()
        if len(queries) == 0:
            break
        queries = list(filter(lambda s: s.startswith('%') or s.startswith('@'), queries))
        if len(queries) == 0:
            continue
        padding = 2 + max(map(lambda q: len(q), queries))
        for query in queries:
            if query in cfg.vars:
                val = cfg[query]
                if query.startswith('%'):
                    rhs = str(val)
                else:
                    rhs = f"0x{val:04x}"

                if query not in qhist:
                    rhs += "  (new)"
                    qhist[query] = val
                elif val != qhist[query]:
                    rhs += f"  (changed from {qhist[query]})"
                    qhist[query] = val
            else:
                rhs = "<undef>"
            pprompt(f"{query: >{padding}} = {rhs}")

