"""
A-Mi optimiser
================
Goldthorpe

This is a proof-of-concept analyser/optimiser for A-Mi
"""

import argparse

from ui.printer import PrinterUI
from ui.reader  import ReaderUI
from ui.opter   import OptUI
from ui.writer  import WriterUI

if __name__ == "__main__":

    ### command-line argument handling ###

    argparser = argparse.ArgumentParser(
                    description="Proof-of-concept optimiser for A-Mi")
    PrinterUI.add_arguments(argparser.add_argument_group("formatting"))
    ReaderUI.add_arguments(argparser.add_argument_group("input"))
    OptUI.add_arguments(argparser.add_argument_group("optimisations"))
    WriterUI.add_arguments(argparser.add_argument_group("output"))

    # managing optimisations

    args = argparser.parse_args()
    PrinterUI(args)
    reader = ReaderUI(args)
    opter = OptUI(args)
    writer = WriterUI(args)

    ### parse source or stdin ###
    reader.fetch_input()
    cfg = reader.build_cfg()

    ### optimise ###
    opter.load_cfg(cfg)
    opter.execute_passes()

    ### print output ###
    writer.write(opter.CFG)
