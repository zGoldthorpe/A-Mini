"""
A-Mi optimiser
================
Goldthorpe

This is a proof-of-concept analyser/optimiser for A-Mi
"""

import argparse
import re
import os
import sys

import ampy.debug    as amd
import ampy.printing as amp
import ampy.reader   as amr
import ampy.types    as amt
import ampy.writer   as amw

from ampy.passmanager import (
        BadArgumentException,
        Pass_ID_re,
        )

from opt import OptManager as OM
from opt.tools import OptList, OptError

### command-line argument handling ###

argparser = argparse.ArgumentParser(
                description="Proof-of-concept optimiser for A-Mi")


argparser.add_argument("--plain",
            dest="format",
            action="store_false",
            help="Print output in plaintext (without ANSI colouring)")
argparser.add_argument("-D", "--debug",
            dest="debug",
            action="store_true",
            help="Enable debug messages")

# handling source code
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

# managing metadata
argparser.add_argument("-M", "--omit-metadata",
            dest="meta",
            action="store_false",
            help="Do not write metadata to output code.")
argparser.add_argument("-f", "--frame",
            dest="frame",
            action="store",
            metavar='"L;W"',
            help="Specify the left margin charwidth and the code window for spacing. "
                 "Use '*' for either dimension to make it automatic.")

# managing optimisations
argparser.add_argument("-o", "--output",
            dest="output",
            action="store",
            type=str,
            help="""Specify destination file for optimised A-Mi code.
                    If omitted, will be printed to STDOUT.""")
argparser.add_argument("-p", "--add-pass",
            dest="passes",
            action="append",
            metavar="[PASS | \"PASS(arg0, arg1, ..., k0=v0, k1=v1, ...)\"]",
            help="""Append a pass to run (order-sensitive).
                    All arguments are passed.""")
argparser.add_argument("-l", "--list-passes",
            dest="ls",
            action="store_true",
            help="List all available passes and exit.")
argparser.add_argument("-?", "--explain",
            dest="explain",
            action="store",
            metavar="PASS",
            help="Provide explanation for a particular pass.")

args = argparser.parse_args()

amd.enabled = args.debug
amp.Printing.can_format &= args.format

### get source code ###
#TODO: make modular

if args.ls:
    amp.psubtle("Optimisation passes:")
    spaces = max(len(opt) for opt in OM)
    for opt in sorted(OM):
        amp.pquery(f"\t{opt: <{spaces}} ", end='')
        amp.phidden(f"({OM[opt].__module__}.{OM[opt].__name__})")
    exit(0)

if args.explain is not None:
    if args.explain in OM:
        amp.psubtle(f"{args.explain} ", end='')
        amp.phidden(f"({OM[args.explain].__module__}.{OM[args.explain].__name__})")
        if OM[args.explain].__doc__ is not None:
            amp.pquery(OM[args.explain].__doc__)
        exit(0)
    amp.perror(f"Unrecognised pass {args.explain}.")
    exit(-8)

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


### optimise ###

passed_analyses = OptList()
if args.passes is not None:
    for opt in args.passes:
        opt_args = []
        opt_kwargs = {}
        m = re.fullmatch(rf"({Pass_ID_re})\((.*)\)", opt)
        if m is not None:
            opt = m.group(1)
            passed = list(map(lambda s:s.strip(), m.group(2).split(',')))
            for arg in passed:
                if '=' not in arg:
                    opt_args.append(arg)
                else:
                    kw, arg = arg.split('=', 1)
                    opt_kwargs[kw] = arg

        if opt in OM:
            try:
                opter = OM[opt](cfg, passed_analyses, *opt_args, **opt_kwargs)
            except BadArgumentException as e:
                amp.perror(f"Optimisation {opt} received invalid argument.\n{e}")
                exit(-7)
            
            try:
                opter.perform_opt()
            except OptError as e:
                amp.perror(f"{opt} discovered an error in source code.\n\t{repr(e.block[e.index])}\n[{e.block.label}:{e.index}] {e.message}")
                exit(-8)

            continue

        amp.perror(f"Unrecognised pass {opt}")
        exit(-9)

### output ###
if args.frame is None:
    tab, code = 4, 96
else:
    try:
        tab, code = args.frame.split(';')
    except:
        tab = '*'
        code = '*'
    try:
        tab = int(tab)
        assert tab >= 0
    except:
        tab = None
    try:
        code = int(code)
        assert code >= 0
    except:
        code = None

writer = amw.CFGWriter(write_meta=args.meta,
        tabwidth=tab, codewidth=code)

if args.output is not None:
    with open(args.output, 'w') as file:
        for line in writer.generate(cfg):
            file.write(f"{line}\n")
else:
    for line in writer.generate(cfg):
        print(line)
