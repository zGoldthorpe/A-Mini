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

    @classmethod
    def arg_init(cls, parsed_args):
        return cls(debug=parsed_args.PUIdebug,
                can_format=parsed_args.PUIformat)


    def __init__(self, debug=False, can_format=True):
        utils.debug.enabled = debug
        utils.printing.Printing.can_format &= can_format

