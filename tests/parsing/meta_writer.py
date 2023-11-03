import sys

from ampy.reader import CFGBuilder
from ampy.writer import CFGWriter
from ampy.printing import tame_whitespace as tw
from tests.tools import PythonExecutionTestSuite

# NB: this test suite assumes that parsing/reader and parsing/meta pass

ts = PythonExecutionTestSuite("parsing/meta_writer")

def lines(s):
    """
    Removes extra whitespace and blank lines and returns a tuple of lines

    s is expected to be a list of lines
    """
    return tuple(filter(lambda s:len(s) > 0,
                (' '.join(line.split()) for line in s)))

def test(prog, expected):
    ts.exec("builder = CFGBuilder()",
            "cfg = builder.build(*prog)",
            "writer = CFGWriter(block_key=lambda B: B.label)",
                # store blocks in alphabetical order, for consistency
            "out = tuple(writer.generate(cfg))",
            "assert lines(expected) == lines(out)",
            state=dict(
                    lines=lines,
                    CFGBuilder=CFGBuilder,
                    CFGWriter=CFGWriter,
                    prog=prog,
                    expected=expected.split('\n')))

basic_prog = [
        ";#!file: something.ami",
        ";#!entrypoint: @A",
        "@A: ;@!parents:",
        "%x = 5 ;%!var_name: x",
        "goto @B ;@!children: @B",
        "@B: %y = 10 ;%!var_name: y",
        "exit ;@!parents: @A",
        ]
# by convention, metavariables are declared in alphabetical order
basic_nice = """
        ;#!entrypoint: @A
        ;#!file: something.ami
        @A:             ;@!children: @B
                        ;@!parents:
            %x = 5      ;%!var_name: x
            goto @B
        @B:             ;@!parents: @A
            %y = 10     ;%!var_name: y
            exit
        """
test(basic_prog,basic_nice)


multi_prog = [
        ";#!author: me myself I",
        "@A: %cond = 1",
        "branch %cond ? @B : @C",
        "@B: goto @D",
        "@C: goto @D",
        "@D: exit ;@!parents: @A @B",
        ]
multi_nice = """
        ;#!author: me myself I
        @A:
            %cond = 1
            branch %cond ? @B : @C
        @B:
            goto @D
        @C:
            goto @D
        @D:         ;@!parents: @A @B
            exit
        """
test(multi_prog, multi_nice)


append_prog = [
        "@A: read %x ;@!x: 44",
        "%a = %x + 1 ;@!x: 45",
        "%b = %x * %x ;@!x: 46",
        ]
append_nice = """
        @A:             ;@!x: 44 45 46
            read %x
            %a = %x + 1
            %b = %x * %x
            exit
        """
test(append_prog, append_nice)


postbranch_prog = [
        "@A: %x = 10 ;%!x: 54",
        ";%!A: 54",
        "goto @B ;%!live: %x",
        ";%!target: @B",
        "@B: exit ;%!dead: %x",
        ]
postbranch_nice = """
        @A:
            %x = 10 ;%!A: 54
                    ;%!x: 54
            goto @B ;%!live: %x
                    ;%!target: @B
        @B:
            exit    ;%!dead: %x
        """
test(postbranch_prog, postbranch_nice)

dollar_prog = [
        ";#!meta: x $ y $ z",
        "@A: %x = 10 ;%!x: 10 $ 30 $ 50 $",
        "goto @B ;%!B: 1 2 3 $ $ 1 2 3",
        "@B: ;@!B: foo $ bar baz $",
        "exit ;#!exit: $ a b c $ d e $ $ $",
        ]
dollar_nice = """
        ;#!exit: $
        ;#!exit: a b c $
        ;#!exit: d e $
        ;#!exit: $
        ;#!exit: $
        ;#!meta: x $
        ;#!meta: y $
        ;#!meta: z
        @A:
            %x = 10 ;%!x: 10 $
                    ;%!x: 30 $
                    ;%!x: 50 $
            goto @B ;%!B: 1 2 3 $
                    ;%!B: $
                    ;%!B: 1 2 3
        @B:         ;@!B: foo $
                    ;@!B: bar baz $
            exit
        """
test(dollar_prog, dollar_nice)


if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
