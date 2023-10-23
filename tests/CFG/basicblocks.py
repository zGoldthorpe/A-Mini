import sys

import ampy.types as amt
from tests.tools import PythonExecutionTestSuite

ts = PythonExecutionTestSuite("basic-blocks")

ts.exec("A = BasicBlock('@A')",
        "B = BasicBlock('@B')",
        "A.add_child(B)",
        "C = BasicBlock('@C')",
        "B.add_child(A)",
        "B.add_child(C, cond='%cond')",
        "C.add_child(C)",
        "C.add_child(A, cond='%cond.2', new_child_if_cond=False)",
        "assert(A.children == BranchTargets(target=B))",
        "assert(B.children == BranchTargets(cond='%cond', iftrue=C, iffalse=A))",
        "assert(C.children == BranchTargets(cond='%cond.2', iftrue=C, iffalse=A))",
        "assert(A.parents == {B, C})",
        "assert(B.parents == {A})",
        "assert(C.parents == {B, C})",
        state=dict(BasicBlock=amt.BasicBlock,
            BranchTargets=amt.BranchTargets))

ts.exec("A = BasicBlock('@A')",
        "B = BasicBlock('@B')",
        "C = BasicBlock('@C')",
        "A.add_child(B)",
        "A.add_child(C, cond='%c')",
        "A.remove_child(B)",
        "assert(A.children == BranchTargets(target=C))",
        "assert(B.parents == set())",
        "assert(C.parents == {A})",
        state=dict(BasicBlock=amt.BasicBlock,
            BranchTargets=amt.BranchTargets))

ts.exec("A = BasicBlock('@A')",
        "B = BasicBlock('@B')",
        "A.add_child(B)",
        "A.add_child(B, cond='%c')",
        "A.remove_child(B)",
        "assert(A.children == BranchTargets())",
        "assert(B.parents == set())",
        state=dict(BasicBlock=amt.BasicBlock,
            BranchTargets=amt.BranchTargets))

ts.exec("A = BasicBlock('@A')",
        "B = BasicBlock('@B')",
        "A.add_child(B)",
        "A.add_child(B, cond='%c')",
        "A.remove_child(B, keep_duplicate=True)",
        "assert(A.children == BranchTargets(target=B))",
        "assert(B.parents == {A})",
        state=dict(BasicBlock=amt.BasicBlock,
            BranchTargets=amt.BranchTargets))

if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
