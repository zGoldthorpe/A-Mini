import sys

from ampy.reader import CFGBuilder
from ampy.printing import tame_whitespace as tw
from tests.tools import PythonExecutionTestSuite

ts = PythonExecutionTestSuite("parsing/meta")

basic_prog = [
        ";#!file: something.ami",
        ";#!entrypoint: @A",
        "@A: ;@!parents:",
        "%x = 5 ;%!var_name: x",
        "goto @B ;@!children: @B",
        "@B: %y = 10 ;%!var_name: y",
        "exit ;@!parents: @A",
        ]
ts.exec("builder = CFGBuilder()",
        "cfg = builder.build(*prog)",
        "assert cfg.meta['file'] == ['something.ami']",
        "assert cfg.meta['entrypoint'] == ['@A']",
        "assert cfg['@A'].meta['parents'] == []",
        "assert cfg['@A'].meta['children'] == ['@B']",
        "assert cfg['@A'][0].meta['var_name'] == ['x']",
        "assert cfg['@B'].meta['parents'] == ['@A']",
        "assert cfg['@B'][0].meta['var_name'] == ['y']",
        state=dict(CFGBuilder=CFGBuilder, prog=basic_prog))

multi_prog = [
        ";#!author: me myself I",
        "@A: %cond = 1",
        "branch %cond ? @B : @C",
        "@B: goto @D",
        "@C: goto @D",
        "@D: exit ;@!parents: @A @B",
        ]
ts.exec("builder = CFGBuilder()",
        "cfg = builder.build(*prog)",
        "assert cfg.meta['author'] == ['me', 'myself', 'I']",
        "assert cfg['@D'].meta['parents'] == ['@A', '@B']",
        state=dict(CFGBuilder=CFGBuilder, prog=multi_prog))

append_prog = [
        "@A: read %x ;@!x: 44",
        "%a = %x + 1 ;@!x: 45",
        "%b = %x * %x ;@!x: 46",
        ]
ts.exec("builder = CFGBuilder()",
        "cfg = builder.build(*prog)",
        "assert cfg['@A'].meta['x'] == ['44', '45', '46']",
        state=dict(CFGBuilder=CFGBuilder, prog=append_prog))

postbranch_prog = [
        "@A: %x = 10 ;%!x: 54",
        ";%!A: 54",
        "goto @B ;%!live: %x",
        ";%!target: @B",
        "@B: exit ;%!dead: %x",
        ]
ts.exec("builder = CFGBuilder()",
        "cfg = builder.build(*prog)",
        "assert cfg['@A'][0].meta['x'] == ['54']",
        "assert cfg['@A'][0].meta['A'] == ['54']",
        "assert 'live' not in cfg['@A'][0].meta",
        "assert cfg['@A'][1].meta['live'] == ['%x']",
        "assert cfg['@A'][1].meta['target'] == ['@B']",
        "assert cfg['@B'][0].meta['dead'] == ['%x']",
        state=dict(CFGBuilder=CFGBuilder, prog=postbranch_prog))

if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
