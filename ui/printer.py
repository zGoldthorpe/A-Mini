"""
Printer
=======
Goldthorpe
"""

import ampy.debug
import ampy.printing

class PrinterUI:
    
    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument("--plain",
                dest="PUI_format",
                action="store_false",
                help="Print output in plaintext (without ANSI colouring)")
        parser.add_argument("-D", "--debug",
                dest="PUI_debug",
                action="store_true",
                help="Enable debug messages")

    def __init__(self, parsed_args):
        ampy.debug.enabled = parsed_args.PUI_debug
        ampy.printing.Printing.can_format &= parsed_args.PUI_format

