import sys
from collections import deque
from difflib import unified_diff

import ampy.types as amt

# === Instructions ===

mov = amt.opcodes['mov']
phi = amt.opcodes['phi']

add = amt.opcodes['add']
sub = amt.opcodes['sub']
mul = amt.opcodes['mul']

eq  = amt.opcodes['eq']
neq = amt.opcodes['neq']
lt  = amt.opcodes['lt']
leq = amt.opcodes['leq']

goto   = amt.opcodes['goto']
branch = amt.opcodes['branch']

read  = amt.opcodes['read']
write = amt.opcodes['write']

brkpt = amt.opcodes['brkpt']

def perror(*args, **kwargs):
    print(f"\033[31m", end='', file=sys.stderr)
    print(*args, **kwargs, file=sys.stderr)
    print("\033[m", end='', file=sys.stderr, flush=True)

def psuccess(*args, **kwargs):
    print(f"\033[32m", end='', file=sys.stderr)
    print(*args, **kwargs, file=sys.stderr)
    print("\033[m", end='', file=sys.stderr, flush=True)

def phead(head):
    print(f"\033[1;4;34m {head} \033[m", file=sys.stderr)

def passert(test, cond, onsuccess="Passed", onfailure="Failed"):
    if cond:
        psuccess(f"[ Assertion {test:02}]:", onsuccess)
    else:
        perror(f"[ Assertion {test}]:", onfailure)
    return cond

def sim_and_test(test, *instructions, initial=amt.VarDict(), expected=None):
    """
    *instructions is a list of type/instruction pairs

    Checks if all instructions run without error, and then
    checks if the final state matches the expectation (if not None)
    """
    success = True
    thead = f"[Simulation {test:02}]:"
    vd = initial
    expass = 0
    for i, (op, instr) in enumerate(instructions):
        cmd = op.read(instr)
        if cmd is None:
            perror(thead+f"[line {i:02}]:", f"Failed to parse \"{instr}\" with {op}")
            continue
        errno = cmd(vd)
        if errno != 0:
            perror(thead+f"[line {i:02}]:", f"\"{instr}\" exited with error code {errno}")
            continue
        expass += 1

    if expass != len(instructions):
        perror(thead, f"{expass} / {len(instructions)} instructions ran without error.")
        success = False
    
    matches = 0
    total = 0
    if expected is not None:
        for key in vd:
            total += 1
            if key not in expected:
                perror(thead, f"Unexpected variable {key} (value {vd[key]}) after execution.")
                continue
            if vd[key] != expected[key]:
                perror(thead, f"Value mismatch for {key}: got {vd[key]}, expected {expected[key]}")
                continue
            matches += 1
        for key in expected:
            if key not in vd:
                total += 1
                perror(thead, f"Missing expected variable {key} (value {expected[key]})")

    if matches != total:
        perror(thead, f"{matches} / {total} match with expected final state.")
        success = False

    if success:
        psuccess(thead, "Passed")

    return success


# dummy I/O classes for testing input and output

_stdin = sys.stdin
_stdout = sys.stdout

_inq = deque()
_outq = deque()

class IOSimulator:
    def __init__(self, feed=None):
        self._q = deque()
        if feed is not None:
            self.feed(feed)
    def readline(self):
        return self._q.popleft()
    def write(self, s):
        self._q.append(s)
    def feed(self, text):
        split = text.split('\n')
        if not split[-1]:
            split.pop()
        for line in split:
            self._q.append(line+'\n')
    def flush(self):
        out = '\n'.join(line for line in self._q)
        return out
    def clear(self):
        self._q.clear()

def set_io_simulation(sim_stdin, sim_stdout):
    sys.stdin = sim_stdin
    sys.stdout = sim_stdout

def reset_io():
    global _stdin, _stdout
    sys.stdin = _stdin
    sys.stdout = _stdout


def sim_with_io(test, *instructions, initial=amt.VarDict(), expected=None, stdin=IOSimulator(), stdout=IOSimulator(), expected_output=None):
    thead = f"[       I/O {test:02}]:"
    
    set_io_simulation(stdin, stdout)
    success = sim_and_test(test,
            *instructions,
            initial=initial,
            expected=expected)
    reset_io()

    unread_inputs = stdin.flush().split()
    if len(unread_inputs) > 0:
        success = False
        perror(thead + " Unread inputs:", *unread_inputs, sep='\n')

    if expected_output is not None:
        output = stdout.flush()
        output_lines = list(map(lambda s: s+'\n', output.split()))
        expect_lines = list(map(lambda s: s+'\n', expected_output.split()))
        diff = [*unified_diff(expect_lines, output_lines, fromfile="Expected output", tofile="Received output")]
        if len(diff) > 0:
            success = False
            perror(thead + " Output discrepancy:\n", *diff, sep='')

    if success:
        psuccess(thead, "Passed")

    return success
