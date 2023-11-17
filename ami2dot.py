"""
A-Mi to DOT
=============
Goldthorpe

Create a DOT file for visualising the control flow graph
for a given A-Mi program.
"""

import argparse

from ui.dot     import DotUI
from ui.printer import PrinterUI
from ui.reader  import ReaderUI
from ui.opter   import OptUI

if __name__ == "__main__":

    ### command-line argument handling ###

    argparser = argparse.ArgumentParser(
                    description="A-Mi to DOT converter")
    ReaderUI.add_arguments(argparser)
    DotUI.add_arguments(argparser.add_argument_group("DOT options"))
    OptUI.add_arguments(argparser.add_argument_group("optimisations"))

    args = argparser.parse_args()

    PrinterUI(debug=False, can_format=False) # disable debug output
    reader = ReaderUI.arg_init(args)
    opter = OptUI.arg_init(args)
    dot = DotUI.arg_init(args)

    ### parse source or stdin ###
    reader.fetch_input()
    cfg = reader.build_cfg()

    ### optimise ###
    opter.load_cfg(cfg)
    opter.execute_passes()

    ### print DOT ###
    dot.print_dot(opter.CFG)

    
