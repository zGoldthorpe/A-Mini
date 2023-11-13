"""
Assembly-Minimal
==================
Goldthorpe

This is a proof-of-concept interpreter for A-Mi
"""

import argparse

from ui.printer import PrinterUI
from ui.reader import ReaderUI
from ui.interpreter import InterpreterUI
from ui.opter import OptUI

if __name__ == "__main__":

    ### command-line argument handling ###

    argparser = argparse.ArgumentParser(
                    description="Proof-of-concept interpreter for A-Mi")

    PrinterUI.add_arguments(argparser.add_argument_group("formatting"))
    ReaderUI.add_arguments(argparser.add_argument_group("input"))
    InterpreterUI.add_arguments(argparser.add_argument_group("interpreter"))
    OptUI.add_arguments(argparser.add_argument_group("optimisation"))

    args = argparser.parse_args()
    PrinterUI(args)
    reader = ReaderUI(args)
    interpreter = InterpreterUI(args)
    opter = OptUI(args)

    ### parse source or stdin ###
    reader.fetch_input()
    cfg = reader.build_cfg()

    ### optimise ###
    opter.load_cfg(cfg)
    opter.execute_passes()

    ### run program ###
    interpreter.load_cfg(opter.CFG)
    interpreter.run()

