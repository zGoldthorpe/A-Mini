import sys

from ampy.reader import CFGBuilder

from analysis.tools import AnalysisList
from analysis.example import ExampleAnalysis, AddLister

from tests.analysis.tools import MetaTestSuite

ts = MetaTestSuite("analysis/example")

ts.analyse_meta(ExampleAnalysis,
        ("add",), dict(count="instructions"),
        [
            "@0: %a = %b + %c",
            "%a = %b * %c",
            "%d = %e + %f",
            "exit",
        ],
        {
            "num_instructions" : ["4"],
            ("@0", "add_indices") : ["0", "2"],
        })

ts.analyse_meta(ExampleAnalysis,
        ("mul",), dict(count="blocks"),
        [
            "@A: %a = %b + %c",
            "    branch %a ? @B : @C",
            "@B: %a = %b * %c",
            "    goto @C",
            "@C: %a = %b * %c",
            "    %_ = %1 * %1",
            "    exit",
        ],
        {
            "num_blocks" : ["3"],
            ("@A", "mul_indices") : [],
            ("@B", "mul_indices") : ["0"],
            ("@C", "mul_indices") : ["0", "1"],
            ("@C", 2, "index") : ["2"],
            ("@A", "add_indices") : None,
        })

prog = [
    "@A:",
        "%a = %b * %c",
        "%b = %a * %c",
        "%e = %f + %f",
        "%g = %e * %f",
        "%w = %u + %v",
    ]
ts.exec("cfg = CFGBuilder().build(*prog)",
        "add_lister = AddLister(cfg, al)",
        "assert add_lister.list_adds('@A') == [cfg['@A'][2], cfg['@A'][4]]",
        "assert len(al) == 1",
        state=dict(CFGBuilder=CFGBuilder,
                    AddLister=AddLister,
                    prog=prog,
                    al=AnalysisList()))

cfg = CFGBuilder().build(*prog)
al = AnalysisList()
ExampleAnalysis(cfg, al, "add", count="blocks")
ts.exec("add_lister = AddLister(cfg, al)",
        "assert add_lister.list_adds('@A') == [cfg['@A'][2], cfg['@A'][4]]",
        "assert len(al) == 1",
        state=dict(cfg=cfg,
                    AddLister=AddLister,
                    prog=prog,
                    al=al))

cfg = CFGBuilder().build(*prog)
al = AnalysisList()
ExampleAnalysis(cfg, al, "mul", count="blocks")
ExampleAnalysis(cfg, al, "mul", count="instructions")
ts.exec("add_lister = AddLister(cfg, al)",
        "assert add_lister.list_adds('@A') == [cfg['@A'][2], cfg['@A'][4]]",
        "assert len(al) == 3",
        state=dict(cfg=cfg,
                    AddLister=AddLister,
                    prog=prog,
                    al=al))

if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
