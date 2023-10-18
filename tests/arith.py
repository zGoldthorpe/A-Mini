from tests._tools import *

phead("Arithmetic test suite")

success = True

vd = [] # to fiddle with final state of each test

vd.append(amt.VarDict())
success |= sim_and_test(0,
        (mov, "%a = 2"),
        (mov, "%b = 5"),
        (mov, "%c = -3"),
        (add, "%sum = %a + %b"),
        (sub, "%diff = %a - %c"),
        (mul, "%prod = %b * %c"),
        initial=vd[0],
        expected = amt.VarDict({
            "#pc" : 0,
            "%a" : 2,
            "%b" : 5,
            "%c" : -3,
            "%sum" : 7,
            "%diff" : 5,
            "%prod" : -15,
            })
        )

vd.append(amt.VarDict())
success |= sim_and_test(1,
        (mov, "%0 = -5"),
        (mov, "%1 = 3"),
        (add, "%sum = %0 + 5"),
        (add, "%sum.1 = 4 + %1"),
        (sub, "%diff = 3 - 10"),
        (sub, "%diff.1 = -1--1"),
        (sub, "%diff.2 = -1-1"),
        (mul, "%prod = 0*0"),
        (mul, "%prod.1 = %0*%1"),
        initial=vd[1],
        expected = amt.VarDict({
            "#pc" : 0,
            "%0" : -5,
            "%1" : 3,
            "%sum" : 0,
            "%sum.1" : 7,
            "%diff" : -7,
            "%diff.1" : 0,
            "%diff.2" : -2,
            "%prod" : 0,
            "%prod.1" : -15,
            })
        )

# Parsing tests
success |= passert(2, add.read("#pc = %a + %b") is None)
success |= passert(3, add.read("%a = #pc + %c") is None)
success |= passert(4, sub.read("%a = -%b") is None)
success |= passert(5, add.read("%a = %b + %c + %d") is None)
success |= passert(6, sub.read("%a = %b + -1") is None)
success |= passert(7, sub.read("%a = ---1") is None)
success |= passert(8, sub.read("%a = -1") is None)
success |= passert(9, mul.read("%a = * 2") is None)
