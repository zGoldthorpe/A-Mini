"""
Optimisation module
=====================
Goldthorpe

This module manages which optimisations are "registered" for use via amo.py
"""

import ampy.passmanager
import opt.tools

### Register optimisations ###

OptManager = ampy.passmanager.PassManager(opt.tools.Opt)

OptManager.register("opt.example.ExampleOpt")
