import sys

import utils.printing

def perror(*args, **kwargs):
    utils.printing.perror(*args, **kwargs, file=sys.stderr)

def die(msg):
    perror(msg)
    exit(99)

def unexpected(exception):
    die(f"Unexpected {type(exception).__name__}:\n\t{exception}")
