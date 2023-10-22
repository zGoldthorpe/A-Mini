import ampy.types as amt

from tests.tools import PythonExecutionTestSuite

ts = PythonExecutionTestSuite("abstract-build")

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

