"""
Opt module
============
Goldthorpe

This module manages which optimisation passes are "registered" for use via amo.py
"""

import ampy.passmanager
import opt.tools

### Register analyses ###

OptManager = ampy.passmanager.PassManager(opt.tools.Opt)

#OptManager.register("opt.example.example_analysis.ExampleAnalysis")
#OptManager.register("opt.example.example_opt.ExampleOpt")

OptManager.register("opt.analysis.domtree.DomTreeAnalysis")
OptManager.register("opt.analysis.defs.DefAnalysis")
OptManager.register("opt.analysis.live.LiveAnalysis")

OptManager.register("opt.simplify.dce.DCE")
OptManager.register("opt.simplify.branch_elim.BranchElim")
OptManager.register("opt.simplify.phi_elim.PhiElim")
OptManager.register("opt.simplify.reg_realloc.RR")

OptManager.register("opt.ssa.SSA")
OptManager.register("opt.gvn.simpson.RPO")
OptManager.register("opt.gvn.simpson.SCC")
OptManager.register("opt.gvn.available_expr.AvailAnalysis")
OptManager.register("opt.gvn.anticipatable.Anticipate")
OptManager.register("opt.gvn.simplify.NaiveSimplify")

