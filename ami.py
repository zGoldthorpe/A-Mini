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

import ampy.debug     as amd
import ampy.interpret as ami
import ampy.printing  as amp
import ampy.reader    as amr
import ampy.types     as amt

from ui.reader import ReaderUI
from ui.interpreter import InterpreterUI

if __name__ == "__main__":

    ### command-line argument handling ###

    argparser = argparse.ArgumentParser(
                    description="Proof-of-concept interpreter for A-Mi")

    argparser.add_argument("--plain",
                dest="format",
                action="store_false",
                help="Print output in plaintext (without ANSI colouring)")
    argparser.add_argument("-D", "--debug",
                dest="debug",
                action="store_true",
                help="Enable debug messages")
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
    argparser.add_argument("--interrupt",
                dest="step",
                choices=("never", "instructions", "blocks"),
                const="blocks",
                default="never",
                nargs="?",
                help="Insert breakpoint at specified frequency (default: never)")

    args = argparser.parse_args()

    amd.enabled = args.debug
    amp.Printing.can_format &= args.format


    ### parse source or stdin ###

    cfg = ReaderUI(args.fname).build_cfg()


    ### run program ###

    InterpreterUI(cfg, args.trace, args.prompt, args.step, args.brkpt).run()

