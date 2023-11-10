import glob
import sys

from ampy.reader import CFGBuilder, AnonymousBlockError
from ampy.printing import tame_whitespace as tw
from tests.tools import PythonExecutionTestSuite

ts = PythonExecutionTestSuite("parsing/reader")

def get_lines(fname):
    with open(fname) as file:
        return file.readlines()

branch_prog = [
        "@A: branch %c ? @B : @C",
        "@B: branch %c ? @C : @D",
        "@C: goto @D",
        "@D: exit",
        ]
ts.exec("builder = CFGBuilder()",
        "cfg = builder.build(*prog)",
        "assert cfg.entrypoint == cfg['@A']",
        "assert cfg['@A'].parents == set()",
        "assert cfg['@B'].parents == {cfg['@A']}",
        "assert cfg['@C'].parents == {cfg['@A'], cfg['@B']}",
        "assert cfg['@D'].parents == {cfg['@B'], cfg['@C']}",
        state=dict(CFGBuilder=CFGBuilder,
                prog=branch_prog))

loop_prog = [
        "@A: branch %c ? @A : @B",
        "@B: goto @C",
        "@C: branch %c ? @B : @D",
        "@D: branch %c ? @E : @A",
        "@E: exit",
        ]
ts.exec("builder = CFGBuilder()",
        "cfg = builder.build(*prog)",
        "assert cfg.entrypoint == cfg['@A']",
        "assert cfg['@A'].parents == {cfg['@A'], cfg['@D']}",
        "assert cfg['@B'].parents == {cfg['@A'], cfg['@C']}",
        "assert cfg['@C'].parents == {cfg['@B']}",
        "assert cfg['@D'].parents == {cfg['@C']}",
        "assert cfg['@E'].parents == {cfg['@D']}",
        state=dict(CFGBuilder=CFGBuilder,
                prog=loop_prog))

fallthrough_prog = [
        "@A:",
        "%x = 5",
        "@B:",
        "%y = 10",
        "@C:",
        "branch %z ? @B : @A",
        ]
ts.exec("builder = CFGBuilder()",
        "cfg = builder.build(*prog)",
        "assert cfg['@B'].parents == {cfg['@A'], cfg['@C']}",
        "assert cfg['@C'].parents == {cfg['@B']}",
        state=dict(CFGBuilder=CFGBuilder,
                prog=fallthrough_prog))

empty_block_prog = [
        "@A: branch %c ? @B : @C",
        "@B:",
        "@C:",
        "goto @D",
        "@D:",
        ]
ts.exec("builder = CFGBuilder()",
        "cfg = builder.build(*prog)",
        "assert cfg['@B'].parents == {cfg['@A']}",
        "assert cfg['@C'].parents == {cfg['@A'], cfg['@B']}",
        state=dict(CFGBuilder=CFGBuilder,
                prog=empty_block_prog))

anon_block_prog = [
        "goto @A",
        "goto @B", # dead code
        "@A: goto @C",
        "@B: goto @C", # dead code
        "branch %c ? @A : @C", # dead code
        "@C: exit",
        ]
ts.exec("builder = CFGBuilder()",
        "cfg = builder.build(*prog)",
        "assert len(cfg) == 3", # 6 - 3 = 3
        "assert len(cfg['@A'].parents) == 1",
        "assert len(cfg['@C'].parents) == 1",
        state=dict(CFGBuilder=CFGBuilder,
                prog=anon_block_prog))
ts.exec("builder = CFGBuilder(allow_anon_blocks=False)",
        ("cfg = builder.build(*prog)", AnonymousBlockError),
        state=dict(CFGBuilder=CFGBuilder,
                prog=anon_block_prog))

phi_prog = [
        "@A: %x.A = 5",
        "goto @C",
        "@B: %x.B = 10", # dead code
        "goto @C",
        "@C: %x = phi [ %x.A, @A ], [ %x.B, @B ]",
        "%y = phi [ %y.A, @A ]",
        "exit"
        ]
ts.exec("builder = CFGBuilder()",
        "cfg = builder.build(*prog)",
        "assert cfg['@C'].parents == {cfg['@A']}",
        state=dict(CFGBuilder=CFGBuilder,
                prog=phi_prog))

### reading tests ###
for fname in sorted(glob.glob("examples/*.ami")):
    ts.exec("builder = CFGBuilder()",
            "cfg = builder.build(*prog)",
            state=dict(CFGBuilder=CFGBuilder,
                    fname=fname, # for testing
                    prog=get_lines(fname)))

if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
