import sys

import ampy.printing

def perror(*args, **kwargs):
    ampy.printing.perror(*args, **kwargs, file=sys.stderr)

def die(msg):
    perror(msg)
    exit(99)

def unexpected(exception):
    die(f"Unexpected {type(exception).__name__}:\n\t{exception}")
