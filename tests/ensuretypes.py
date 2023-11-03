import sys

from ampy.ensuretypes import Syntax, Assertion
from ampy.printing import tame_whitespace as tw
from tests.tools import PythonExecutionTestSuite

ts = PythonExecutionTestSuite("ensuretypes")

ts.exec(tw("""
        @Syntax(int)
        def foo(x):
            return x"""),
        "foo(0)",
        ("foo('a')", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax((int, float))
        def foo(x): return x"""),
        "foo(0)",
        "foo(0.)",
        ("foo('a')", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax(((), int, float, int)).returns(((), str, float))
        def foo(t): return str(t[0] + t[2]), t[1]"""),
        "assert foo((1, 2., 3)) == ('4', 2.)",
        ("foo((1, 2, 3))", TypeError),
        ("foo(1, 2., 3)", TypeError),
        ("foo((1., 2., 3.))", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax([list, int, [2, 5]])
        def foo(ls):
            s = 0
            for i in range(len(ls)):
                s += ls[i]
            return s"""),
        "foo([1, 2])",
        "foo([1,2,3,4,5])",
        ("foo([1])", TypeError),
        ("foo([1,2,3,4,5,6])", TypeError),
        ("foo(0)", TypeError),
        ("foo([1., 2, 3])", TypeError),
        ("foo([1, 2, 3.])", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax([int])
        def foo(ls):
            m = 0
            for x in ls:
                m = x if m < x else m
            return m"""),
        "foo([])",
        "foo([0])",
        "foo([0]*1000)",
        ("foo(0)", TypeError),
        ("foo([1, 2, 3.])", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax([str, [..., 3]])
        def foo(ls):
            m = 0
            for x in ls:
                y = len(x)
                m = y if m < y else m
            return m"""),
        "foo([])",
        "foo(['a'])",
        "foo(['a', 'b', 'c'])",
        "foo('abc')", # bug, or feature?
        ("foo(0)", TypeError),
        ("foo(['a', 'b', 'c', 'd'])", TypeError),
        ("foo(['a', 'b', 0])", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax(int).returns([set, int])
        def foo(x): return {x, x**x}"""),
        "assert foo(3) == {3, 27}",
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax(int, ...).returns(int)
        def foo(*x): return len(x)"""),
        "assert foo() == 0",
        "assert foo(1) == 1",
        "assert foo(1, 2) == 2",
        "assert foo(*[1, 2, 3]) == 3",
        ("foo(1, 2, 'a')", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax(int, str, ..., int).returns(int)
        def foo(*x): return x[0] + x[-1]"""),
        "assert foo(1, 2) == 3",
        "assert foo(1, 'a', 2) == 3",
        "assert foo(1, 'a', 'b', 2) == 3",
        ("foo(1)", TypeError),
        ("foo(1, 'a')", TypeError),
        ("foo('a', 2)", TypeError),
        ("foo(1, 'a', 2, 'b', 3)", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @(Syntax([iter, int]) >> int)
        def foo(gen): return sum(gen)"""),
        "assert foo(i for i in range(5)) == 10",
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @(Syntax(int) >> None)
        def foo(x): pass"""),
        "foo(0)",
        ("foo('a')", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @(Syntax(int) >> [iter, int])
        def foo(N):
            for i in range(N):
                yield i"""),
        "assert list(foo(3)) == [0, 1, 2]",
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @(Syntax(int) >> [iter, int])
        def bad(N):
            for i in range(N):
                yield i
            yield 'hello'"""),
        ("list(bad(3))", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax({str:int}, int).returns(int)
        def foo(dc, N):
            n = 0
            for k in dc:
                if int(dc[k]) < N:
                    n += 1
            return n"""),
        "assert foo(dict(a=3, b=5, c=10), 8) == 2",
        ("foo(dict(a=3, b=5, c='10'), 8)", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax(r"h[ae]y[!?]?").returns("hi")
        def foo(s): return 'hi'"""),
        "assert foo('hey') == 'hi'",
        "assert foo('hay?') == 'hi'",
        "assert foo('hey!') == 'hi'",
        ("foo('haey')", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax(slice([int], int, None)).returns(slice(int, [int], int))
        def foo(sl):
            return slice(sl.stop, list(reversed(sl.start)), len(sl.start))"""),
        "assert foo(slice([1,2,3], 4)) == slice(4, [3,2,1], 3)",
        ("foo(slice([], 1, 1))", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax(((), [int], [str]), int).returns(((), int, int))
        def foo(t, x):
            u = [n for n in t[0]]
            v = [s for s in t[1]] # needed for processing
            return len(u)+x, len(v)+x"""),
        "assert foo([[1, 2], ['a', 'b']], 1) == (3, 3)",
        "assert foo(([], []), 4) == (4, 4)",
        ("foo([[1, 2.], ['a', 'b']], 1)", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax(lambda:Syntax(int)>>int, int).returns(int)
        def foo(func, x): return func(x)"""),
        "assert foo(lambda x: x+1, 0) == 1",
        ("foo(lambda:0, 5)", TypeError),
        ("foo(lambda x, y: x+y, 5)", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax(lambda:Syntax(int)>>str,
                lambda:Syntax(str)>>int
                ).returns([tuple, lambda:Syntax(object), 2])
        def foo(func0, func1):
            return (
                lambda n: func1(func0(n)),
                lambda s: func0(func1(s)),
            )"""),
        "f, g = foo(lambda x:str(x), lambda s:len(s))",
        "assert f(10) == 2",
        "assert g('10') == '2'",
        ("f('10')", TypeError),
        ("g(10)", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax(int).set_allow_extra_kwargs(True, float).returns(float)
        def foo(x, **kwargs):
            y = float(x)
            for z in kwargs.values():
                y += z
            return y"""),
        "assert foo(3, g=1., h=2.) == 6.",
        ("foo(3, g=5)", TypeError),
        ("foo(5, a=2., b='h')", TypeError),
        state=dict(Syntax=Syntax))

ts.exec(tw("""
        @Syntax(Assertion(lambda x: len(x) == 5)).returns(Assertion(lambda x: len(x) == 2 and x[0] <= x[1]))
        def foo(ls): return (min(ls), max(ls))"""),
        "assert foo([3, 2, 5, 4, 1]) == (1, 5)",
        ("foo([1, 2, 3, 4])", TypeError),
        state=dict(Syntax=Syntax,Assertion=Assertion))

if __name__ == "__main__":
    ts.print_results()
    if not sys.flags.interactive:
        sys.exit(0 if ts.all_tests_passed else -1)
