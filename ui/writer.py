"""
Writer
========
Goldthorpe
"""

import utils.printing

from ui.errors import perror, die, unexpected

import ampy.writer
import ampy.types

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

    @classmethod
    def arg_init(cls, parsed_args):
        return cls(frame=parsed_args.WUIframe,
                meta=parsed_args.WUImeta,
                fname=parsed_args.WUIoutput)

    def __init__(self, frame=None, meta=True, fname=None):
        # parse frame formatting
        if frame is None:
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
                write_meta=meta,
                tabwidth=tab, codewidth=code)
        self._fname = fname

    def write(self, cfg):
        if self._fname is not None:
            with open(self._fname, 'w') as file:
                for line in self._writer.generate(cfg):
                    file.write(f"{line}\n")
        else:
            for line in self._writer.generate(cfg):
                print(line)
