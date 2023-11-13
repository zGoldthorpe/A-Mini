"""
Writer
========
Goldthorpe
"""

import ampy.printing
import ampy.writer
import ampy.types

from ui.errors import perror, die, unexpected

class WriterUI:

    @classmethod
    def add_arguments(self, parser):
        parser.add_argument("-M", "--omit-metadata",
                dest="WUImeta",
                action="store_false",
                help="Do not write metadata to output code.")
        parser.add_argument("-f", "--frame",
                dest="WUIframe",
                action="store",
                metavar='"L;W"',
                help="Specify the left margin charwidth and the code window for spacing. "
                     "Use '*' for either dimension to make it automatic.")
        parser.add_argument("-o", "--output",
                dest="WUIoutput",
                action="store",
                type=str,
                help="""Specify destination file for optimised A-Mi code.
                        If omitted, will be printed to STDOUT.""")

    def __init__(self, parsed_args):
        # parse frame formatting
        if parsed_args.WUIframe is None:
            tab, code = 4, 96 # good ol' hardcoded integers
        else:
            try:
                tab, code = args.WUIframe.split(';')
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

        self._writer = ampy.writer.CFGWriter(
                write_meta=parsed_args.WUImeta,
                tabwidth=tab, codewidth=code)
        self._fname = parsed_args.WUIoutput

    def write(self, cfg):
        if self._fname is not None:
            with open(self._fname, 'w') as file:
                for line in self._writer.generate(cfg):
                    file.write(f"{line}\n")
        else:
            for line in self._writer.generate(cfg):
                print(line)
