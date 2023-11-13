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

import ampy.debug
import ampy.printing

from ui.printer import PrinterUI
from ui.reader import ReaderUI
from ui.interpreter import InterpreterUI

if __name__ == "__main__":

    ### command-line argument handling ###

    argparser = argparse.ArgumentParser(
                    description="Proof-of-concept interpreter for A-Mi")
    PrinterUI.add_arguments(argparser)
    ReaderUI.add_arguments(argparser)
    InterpreterUI.add_arguments(argparser)


    args = argparser.parse_args()
    
    PrinterUI(args)

    ### parse source or stdin ###

    cfg = ReaderUI(args).build_cfg()

    ### run program ###

    InterpreterUI(cfg, args).run()

