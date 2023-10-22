from ampy.types import BasicBlock

from tests.tools import TestSuite

ts = TestSuite("abstract-build")

ts.exec("A = BasicBlock('@A')",
        "B = BasicBlock('@B')",
        "A.add_child(B)",
        "C = BasicBlock('@C')",
        "B.add_child(A)",
        "B.add_child(C, cond='%cond')",
        "C.add_child(C)",
        "C.add_child(A, cond='%cond.2', new_child_if_cond=False)",
        state=dict(BasicBlock=BasicBlock))

