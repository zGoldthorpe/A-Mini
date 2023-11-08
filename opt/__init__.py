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

OptManager.register("opt.analysis.example_analysis.ExampleAnalysis")
OptManager.register("opt.analysis.domtree.DomTreeAnalysis")
OptManager.register("opt.analysis.defs.DefAnalysis")
OptManager.register("opt.analysis.live.LiveAnalysis")

OptManager.register("opt.example_opt.ExampleOpt")
OptManager.register("opt.ssa.SSA")
