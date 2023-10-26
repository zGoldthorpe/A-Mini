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


def tame_whitespace(src:str, indent_second_line=False, tab_width=4):
    """
    Intended for multi-line strings (messages, source code, etc.)

    Assumes second line and onward has poor indentation due to string
    being defined with triple quotes and given multiline.

    Returns "intended" string for src.
    """
    lines = src.split('\n')
    if len(lines) == 0:
        return ""
    lines[0] = ' '.join(lines[0].split())
    if len(lines) == 1:
        return lines[0]

    wc = 0 # count whitespace
    while lines[1][wc] == ' ':
        wc += 1

    if indent_second_line:
        wc -= tab_width # it's OK if wc < 0

    for i in range(1, len(lines)):
        if lines[i].strip() == "":
            lines[i] = ""
            continue
        wci = 0
        while lines[i][wci] == ' ':
            wci += 1
        if wci < wc:
            raise IndentationError(f"Cannot resolve indentation on line {i}")
        lines[i] = ' '*(wci-wc) + ' '.join(lines[i].split())

    if lines[0] == "":
        return '\n'.join(lines[1:])
    return '\n'.join(lines)
