from tests._tools import *

phead("Comparison test suite")

success = True

vd = []

vd.append(amt.VarDict())
success |= sim_and_test(0,
        (mov, "%a = 1"),
        (mov, "%b = -3"),
        (mov, "%c = 6"),
        (eq,  "%eq = %a == %b"),
        (eq,  "%eq.1 = %a == 1"),
        (eq,  "%eq.2 = -3 == %b"),
        (eq,  "%eq.3 = -2==-2"),
        (neq, "%neq = %b != %b"),
        (lt,  "%lt = %b < 0"),
        (lt,  "%lt.2 = %c < 6"),
        (leq, "%leq = %c <= 6"),
        (leq, "%leq.2 = %b <= 0"),
        initial=vd[0],
        expected = amt.VarDict({
            "#pc" : 0,
            "%a" : 1,
            "%b" : -3,
            "%c" : 6,
            "%eq" : 0,
            "%eq.1" : 1,
            "%eq.2" : 1,
            "%eq.3" : 1,
            "%neq" : 0,
            "%lt" : 1,
            "%lt.2" : 0,
            "%leq" : 1,
            "%leq.2" : 1,
            })
        )
