"""
Debug messages
================
Simple generic debug message generator

Set utils.debug.enabled to toggle debug statements (default: False)
Set utils.debug.file to specify output destination (default: sys.stderr)
"""

import sys

import utils.printing

enabled = False

def print(obj, *args, print_func=None, **kwargs):
    global enabled
    if enabled:
        if print_func is None:
            print_func = utils.printing.pdebug

        print_func(obj, "::", *args, **kwargs, file=sys.stderr)
