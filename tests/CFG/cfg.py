import sys

import ampy.types as amt
from tests.tools import PythonExecutionTestSuite

ts = PythonExecutionTestSuite("CFG/cfg")

ts.exec("cfg = amt.CFG()",
        "cfg.add_block('@A')",
        "cfg.add_block('@B')",
        "cfg.set_entrypoint('@A')",
        "assert(cfg.entrypoint == cfg['@A'])",
        state=dict(amt=amt))

ts.exec("cfg = amt.CFG()",
        """cfg.add_block('@A',
            amt.AddInstruction('%sum', '%a', '%b'),
            amt.LtInstruction('%cond', '%sum', '%foo'),
            amt.BranchInstruction('%cond', '@B', '@C'))""",
        """cfg.add_block('@B',
            amt.MulInstruction('%prod.1', '%x', '%y'),
            amt.GotoInstruction('@D'))""",
        """cfg.add_block('@C',
            amt.MulInstruction('%prod.2', '%u', '%v'),
            amt.GotoInstruction('@D'))""",
        """cfg.add_block('@D',
            amt.PhiInstruction('%prod', ('%prod.1', '@B'), ('%prod.2', '@C')),
            amt.WriteInstruction('%prod'))""",
        "cfg.set_entrypoint('@A')",
        """assert(cfg['@A'].children == amt.BranchTargets(
                                    cond='%cond',
                                    iftrue=cfg['@B'],
                                    iffalse=cfg['@C']))""",
        "assert(cfg['@B'].children == amt.BranchTargets(target=cfg['@D']))",
        "assert(cfg['@C'].children == amt.BranchTargets(target=cfg['@D']))",
        "assert(cfg['@D'].children == amt.BranchTargets())",
        "assert(cfg['@A'].parents == set())",
        "assert(cfg['@B'].parents == {cfg['@A']})",
        "assert(cfg['@C'].parents == {cfg['@A']})",
        "assert(cfg['@D'].parents == {cfg['@B'], cfg['@C']})",
        state=dict(amt=amt))

if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
