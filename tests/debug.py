from tests._tools import *

phead("Debug test suite")

# this only tests that breakpoints do not affect a program
# and that it parses correctly

success = True

vd = []
stdin = []
stdout = []

vd.append(amt.VarDict())
stdin.append(IOSimulator('\n'))
stdout.append(IOSimulator())
success |= sim_with_io(0,
        (brkpt, "brkpt !breakpoint"),
        initial=vd[0],
        stdin=stdin[0],
        stdout=stdout[0],
        )

vd.append(amt.VarDict())
stdin.append(IOSimulator('\n'))
stdout.append(IOSimulator())
success |= sim_with_io(1,
        (mov, "%a = 1"),
        (brkpt, "brkpt !0"),
        (mov, "%b = 5"),
        initial=vd[1],
        stdin=stdin[1],
        stdout=stdout[1],
        expected = amt.VarDict({
            "#pc" : 0,
            "%a" : 1,
            "%b" : 5,
            })
        )

vd.append(amt.VarDict())
stdin.append(IOSimulator("5\n\n4\n"))
stdout.append(IOSimulator())
success |= sim_with_io(2,
        (read, "read %a"),
        (brkpt, "brkpt !after.read"),
        (read, "read %b"),
        initial=vd[2],
        stdin=stdin[2],
        stdout=stdout[2],
        expected = amt.VarDict({
            "#pc" : 0,
            "%a" : 5,
            "%b" : 4,
            })
        )

vd.append(amt.VarDict())
stdin.append(IOSimulator("5\n0\n4\n"))
stdout.append(IOSimulator())
success |= sim_with_io(3,
        (read, "read %a"),
        (brkpt, "brkpt !."),
        (read, "read %b"),
        initial=vd[3],
        stdin=stdin[3],
        stdout=stdout[3],
        expected = amt.VarDict({
            "#pc" : 0,
            "%a" : 5,
            "%b" : 4,
            })
        )

# Parsing tests
success |= passert(4, brkpt.read("brkpt") is None)
success |= passert(5, brkpt.read("brkpt foo") is None)
success |= passert(6, brkpt.read("brkpt %ax") is None)
success |= passert(7, brkpt.read("brkpt !!") is None)
success |= passert(8, brkpt.read("brkpt !hi followup") is None)
success |= passert(9, brkpt.read("brkpt !") is None)
