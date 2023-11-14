"""
Printer
=======
Goldthorpe
"""

import utils.debug
import utils.printing

class PrinterUI:
    
    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument("--plain",
                dest="PUIformat",
                action="store_false",
                help="Print output in plaintext (without ANSI colouring)")
        parser.add_argument("-D", "--debug",
                dest="PUIdebug",
                action="store_true",
                help="Enable debug messages")

    def __init__(self, parsed_args):
        utils.debug.enabled = parsed_args.PUIdebug
        utils.printing.Printing.can_format &= parsed_args.PUIformat

