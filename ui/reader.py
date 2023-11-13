"""
Reader
========
Goldthorpe
"""

import os
import sys

import utils.printing

from ui.errors import perror, die, unexpected

import ampy.reader
import ampy.types

class ReaderUI:

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument("fname",
                metavar="<prog.ami>",
                nargs="?",
                help="""File containing plaintext A-Mi instructions.
                        If omitted, code will be read through STDIN.""")

    def __init__(self, parsed_args):
        self._instructions = []
        self._fname = parsed_args.fname

    def fetch_input(self):
        """
        Obtain input from file or STDIN.
        """
        if self._fname is None:
            self.fname = "<stdin>"
            self._read_input()
        else:
            self.fname = self._fname
            self._read_file_lines()

    def build_cfg(self):
        """
        Build the CFG from the read input
        """
        builder = ampy.reader.CFGBuilder()
        try:
            return builder.build(*self._instructions)
        except ampy.reader.EmptyCFGError:
            die("Program is empty!")
        except ampy.reader.NoEntryPointError as e:
            die(e.message)
        except ampy.reader.AnonymousBlockError as e:
            perror(f"{self.fname}::{e.line+1}:", self._instructions[e.line])
            die("All basic blocks must be explicitly labelled.")
        except ampy.reader.ParseError as e:
            perror(f"{self.fname}::{e.line+1}:", self._instructions[e.line])
            die(e.message)
        except ampy.types.BadPhiError as e:
            die(f"{self.fname}: {e.message}")
        except Exception as e:
            unexpected(e)



    def _read_file_lines(self):
        """
        Read from a file and return the list of inputs.
        """
        if not os.path.exists(self.fname):
            die("Source file {self.fname} does not exist.")
        if not os.path.isfile(self.fname):
            die(f"{self.fname} is not a file!")
        with open(self.fname, 'r') as file:
            self._instructions = list(ln.strip() for ln in file.readlines())

    def _read_input(self):
        """
        Simple and pretty CLI for getting instructions from STDIN
        """
        utils.printing.pprompt(utils.printing.tame_whitespace("""
            Enter A-Mi instructions below.
            Press Ctrl-D to end input, and Ctrl-C to cancel."""))
        while True:
            utils.printing.pprompt(f"{len(self._instructions)+1: >4d} | ", end='', flush=True)
            try:
                self._instructions.append(input().strip())
            except KeyboardInterrupt:
                # ^C
                print()
                exit()
            except EOFError:
                # ^D
                print()
                break
            except Exception as e:
                print()
                unexpected(e)
