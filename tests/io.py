from tests._tools import *

phead("I/O test suite")

success = True

vd = []
stdin = []
stdout = []

vd.append(amt.VarDict())
stdin.append(IOSimulator("5\n"))
stdout.append(IOSimulator())
success |= sim_with_io(0,
        (read, "read %a"),
        initial=vd[0],
        stdin=stdin[0],
        stdout=stdout[0],
        expected=amt.VarDict({
            "#pc" : 0,
            "%a" : 5,
            })
        )

vd.append(amt.VarDict())
stdin.append(IOSimulator())
stdout.append(IOSimulator())
success |= sim_with_io(1,
        (mov, "%a = 5"),
        (write, "write %a"),
        initial=vd[1],
        stdin=stdin[1],
        stdout=stdout[1],
        expected_output="5\n",
        )

vd.append(amt.VarDict())
stdin.append(IOSimulator())
stdout.append(IOSimulator())
success |= sim_with_io(2,
        (write, "write -10"),
        initial=vd[2],
        stdin=stdin[2],
        stdout=stdout[2],
        expected_output="-10\n",
        )

vd.append(amt.VarDict())
stdin.append(IOSimulator("-6\n"))
stdout.append(IOSimulator())
success |= sim_with_io(3,
        (read, "read %a"),
        (add, "%b = %a + 1"),
        (write, "write %b"),
        initial=vd[3],
        stdin=stdin[3],
        stdout=stdout[3],
        expected_output="-5\n",
        expected=amt.VarDict({
            "#pc" : 0,
            "%a" : -6,
            "%b" : -5,
            })
        )

# Parsing tests
success |= passert(4, read.read("read #pc") is None)
success |= passert(5, read.read("read -30") is None)
success |= passert(6, write.read("write #pc") is None)
success |= passert(7, write.read("write") is None)
