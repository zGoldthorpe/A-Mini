"""
Debug messages
================
Simple generic debug message generator

Set debug.enabled to toggle debug statements (default: False)
Set debug.file to specify output destination (default: sys.stderr)
"""

import sys

import ampy.printing

enabled = False
file = sys.stderr

def print(obj, *args, **kwargs):
    global enabled, file
    if enabled:
        ampy.printing.pdebug(repr(obj), "::", *args, **kwargs, file=file)
