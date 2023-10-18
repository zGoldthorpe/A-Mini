from tests._tools import *

phead("Phi test suite")

success = True

vd = []

vd.append(amt.VarDict({"@entry" : 1, "@jmp" : 5}))
success |= sim_and_test(0,
        (goto, "goto @entry"),
        (goto, "goto @jmp"),
        (phi, "%p = phi [3, @entry]"),
        initial=vd[0],
        expected = amt.VarDict({
            "#pc" : 5,
            "%p" : 3,
            "@entry" : 1,
            "@jmp" : 5,
            })
        )

vd.append(amt.VarDict({"@entry" : 1, "@jmp" : 5, "@jmp.2" : 10}))
success |= sim_and_test(1,
        (goto, "goto @entry"),
        (goto, "goto @jmp"),
        (goto, "goto @jmp.2"),
        (phi, "%p = phi [3, @entry], [-1, @jmp]"),
        initial=vd[1],
        expected = amt.VarDict({
            "#pc" : 10,
            "%p" : -1,
            "@entry" : 1,
            "@jmp" : 5,
            "@jmp.2" : 10,
            })
        )

vd.append(amt.VarDict({"@jmp" : 1, "@jmp.2" : 5, "@jmp.3" : 10}))
success |= sim_and_test(2,
        (goto, "goto @jmp"),
        (goto, "goto @jmp.2"),
        (goto, "goto @jmp.3"),
        (phi, "%p = phi [-6, @jmp], [3,@jmp.3], [ 0, @jmp.2 ]"),
        initial=vd[2],
        expected = amt.VarDict({
            "#pc" : 10,
            "%p" : 0,
            "@jmp" : 1,
            "@jmp.2" : 5,
            "@jmp.3" : 10,
            })
        )

vd.append(amt.VarDict({"@jmp" : 1, "@jmp.2" : 5, "@jmp.3" : 10}))
success |= sim_and_test(3,
        (goto, "goto @jmp"),
        (goto, "goto @jmp.2"),
        (goto, "goto @jmp.3"),
        (phi, "%p = phi [0, @jmp.2], [-6, @jmp], [3, @jmp.3]"),
        initial=vd[3],
        expected = amt.VarDict({
            "#pc" : 10,
            "%p" : 0,
            "@jmp" : 1,
            "@jmp.2" : 5,
            "@jmp.3" : 10,
            })
        )

vd.append(amt.VarDict({"@jmp" : 1, "@jmp.2" : 5}))
success |= sim_and_test(4,
        (goto, "goto @jmp"),
        (goto, "goto @jmp.2"),
        (mov, "%0 = 6"),
        (mov, "%1 = 8"),
        (phi, "%p = phi [ %0, @jmp ], [ %1, @jmp.2 ]"),
        initial=vd[4],
        expected = amt.VarDict({
            "#pc" : 5,
            "%0" : 6,
            "%1" : 8,
            "%p" : 6,
            "@jmp" : 1,
            "@jmp.2" : 5,
            })
        )

# Parsing tests
success |= passert( 5, phi.read("phi [0, 0]") is None)
success |= passert( 6, phi.read("phi [%a, 0]") is None)
success |= passert( 7, phi.read("phi [%a, @b, @c]") is None)
success |= passert( 8, phi.read("phi [%a,]") is None)
success |= passert( 9, phi.read("phi ") is None)
success |= passert(10, phi.read("phi [%a, [%b, @c]") is None)
success |= passert(11, phi.read("phi [@a, @b]") is None)
success |= passert(12, phi.read("phi []") is None)
