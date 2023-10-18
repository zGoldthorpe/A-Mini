from tests._tools import *

phead("Branch test suite")

success = True

vd = []

vd.append(amt.VarDict({"@label" : 5}))
success |= sim_and_test(0,
        (goto, "goto @label"),
        initial=vd[0],
        expected = amt.VarDict({
            "#pc" : 5,
            "@label" : 5,
            })
        )

vd.append(amt.VarDict({"@lbl1" : 5, "@lbl2" : 8}))
success |= sim_and_test(1,
        (mov, "%cond = 1"),
        (branch, "branch %cond ? @lbl1 : @lbl2"),
        initial=vd[1],
        expected = amt.VarDict({
            "#pc" : 5,
            "%cond" : 1,
            "@lbl1" : 5,
            "@lbl2" : 8,
            })
        )

vd.append(amt.VarDict({"@lbl1" : 5, "@lbl2" : 8}))
success |= sim_and_test(2,
        (mov, "%cond = 0"),
        (branch, "branch %cond?@lbl1:@lbl2"),
        initial=vd[2],
        expected = amt.VarDict({
            "#pc" : 8,
            "%cond" : 0,
            "@lbl1" : 5,
            "@lbl2" : 8,
            })
        )

vd.append(amt.VarDict({"@lbl1" : 5, "@lbl2" : 8}))
success |= sim_and_test(3,
        (mov, "%cond = -1"),
        (branch, "branch %cond ? @lbl1 : @lbl2"),
        initial=vd[3],
        expected = amt.VarDict({
            "#pc" : 5,
            "%cond" : -1,
            "@lbl1" : 5,
            "@lbl2" : 8,
            })
        )

vd.append(amt.VarDict({"@jmp" : 5, "@jmp.1" : 15}))
success |= sim_and_test(4,
        (goto, "goto @jmp"),
        (goto, "goto @jmp.1"),
        initial=vd[4],
        expected = amt.VarDict({
            "#pc" : 15,
            "@jmp" : 5,
            "@jmp.1" : 15,
            })
        )

vd.append(amt.VarDict({"@lbl" : 5, "@_" : 0, "@lbl.1" : 15}))
success |= sim_and_test(5,
        (mov, "%cond = 1"),
        (branch, "branch %cond ? @lbl : @_"),
        (branch, "branch %cond ? @lbl.1 : @lbl"),
        initial=vd[5],
        expected = amt.VarDict({
            "#pc" : 15,
            "%cond" : 1,
            "@_" : 0,
            "@lbl" : 5,
            "@lbl.1" : 15,
            })
        )

vd.append(amt.VarDict({"@lbl" : 5, "@_" : 0, "@lbl.1" : 15}))
success |= sim_and_test(6,
        (mov, "%cond = 0"),
        (goto, "goto @lbl"),
        (branch, "branch %cond ? @_ : @lbl.1"),
        initial=vd[6],
        expected = amt.VarDict({
            "#pc" : 15,
            "%cond" : 0,
            "@_" : 0,
            "@lbl" : 5,
            "@lbl.1" : 15,
            })
        )

vd.append(amt.VarDict({"@_" : 0, "@entry" : 6, "@entry.2" : 16}))
success |= sim_and_test(7,
        (branch, "branch 1 ? @entry : @_"),
        (branch, "branch 0 ? @_ : @entry.2"),
        initial=vd[7],
        expected = amt.VarDict({
            "#pc" : 16,
            "@_" : 0,
            "@entry" : 6,
            "@entry.2" : 16,
            })
        )

# Parsing tests
success |= passert( 8, goto.read("goto #pc") is None)
success |= passert( 9, goto.read("goto 7") is None)
success |= passert(10, branch.read("branch %a ? @cond") is None)
success |= passert(11, branch.read("branch %a ?: @cond") is None)
success |= passert(12, branch.read("branch ? @a : @b") is None)
success |= passert(13, branch.read("branch %a ? 0 : 1") is None)
success |= passert(14, branch.read("branch %a ? @b : 0") is None)
success |= passert(15, branch.read("branch %a ? 1 : @c") is None)
success |= passert(16, branch.read("branch %a ? #pc : @b") is None)
success |= passert(17, branch.read("branch @a ? @b : @c") is None)
success |= passert(18, branch.read("branch %a ? %b : @c") is None)
