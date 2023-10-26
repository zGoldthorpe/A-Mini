"""
Simple module for formatted printing (only supporting linux)
"""
import sys

def _can_format():
    return sys.platform.startswith("linux")

class Printing:

    # class variable to toggle formatting
    can_format = sys.platform.startswith("linux")

    def formatted(at_begin, at_end, *args, file=sys.stdout, flush=True, **kwargs):
        if Printing.can_format:
            print(at_begin, end='', file=file)

        print(*args, file=file, flush=flush, **kwargs)

        if Printing.can_format:
            print(at_end, end='', file=file, flush=flush)

### special cases ###

def psubtle(*args, **kwargs):
    Printing.formatted("\033[33m", "\033[m", *args, **kwargs)
def pprompt(*args, **kwargs):
    Printing.formatted("\033[34m", "\033[m", *args, **kwargs)
def psuccess(*args, **kwargs):
    Printing.formatted("\033[32m", "\033[m", *args, **kwargs)
def perror(*args, **kwargs):
    Printing.formatted("\033[31m", "\033[m", *args, **kwargs)
