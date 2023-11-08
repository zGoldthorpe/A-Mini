import sys

import ampy.types as amt
from tests.tools import PythonExecutionTestSuite

ts = PythonExecutionTestSuite("CFG/basicblocks")

ts.exec("cfg = CFG()",
        "A = cfg.fetch_or_create_block('@A')",
        "B = cfg.fetch_or_create_block('@B')",
        "A.add_child(B)",
        "C = cfg.fetch_or_create_block('@C')",
        "B.add_child(A)",
        "B.add_child(C, cond='%cond')",
        "C.add_child(C)",
        "C.add_child(A, cond='%cond.2', new_child_if_cond=False)",
        "assert(A.children == (B,))",
        "assert(B.children == (A, C))", # iffalse, then iftrue
        "assert(C.children == (A, C))",
        "assert(A.parents == {B, C})",
        "assert(B.parents == {A})",
        "assert(C.parents == {B, C})",
        state=dict(CFG=amt.CFG))

ts.exec("cfg = CFG()",
        "A = cfg.fetch_or_create_block('@A')",
        "B = cfg.fetch_or_create_block('@B')",
        "C = cfg.fetch_or_create_block('@C')",
        "A.add_child(B)",
        "A.add_child(C, cond='%c')",
        "A.remove_child(B)",
        "assert(A.children == (C,))",
        "assert(B.parents == set())",
        "assert(C.parents == {A})",
        state=dict(CFG=amt.CFG))

ts.exec("cfg = CFG()",
        "A = cfg.fetch_or_create_block('@A')",
        "B = cfg.fetch_or_create_block('@B')",
        "A.add_child(B)",
        "A.add_child(B, cond='%c')",
        "A.remove_child(B)",
        "assert(A.children == ())",
        "assert(B.parents == set())",
        state=dict(CFG=amt.CFG))

ts.exec("cfg = CFG()",
        "A = cfg.fetch_or_create_block('@A')",
        "B = cfg.fetch_or_create_block('@B')",
        "A.add_child(B)",
        "A.add_child(B, cond='%c')",
        "A.remove_child(B, keep_duplicate=True)",
        "assert(A.children == (B,))",
        "assert(B.parents == {A})",
        state=dict(CFG=amt.CFG))

if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
