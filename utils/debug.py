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

def print(obj, *args, **kwargs):
    global enabled
    if enabled:
        utils.printing.pdebug(obj, "::", *args, **kwargs, file=sys.stderr)
