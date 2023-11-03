"""
Analysis module
=================
Goldthorpe

This module manages which analyses are "registered" for use via amo.py
"""

import ampy.passmanager
import analysis.tools

### Register analyses ###

AnalysisManager = ampy.passmanager.PassManager(analysis.tools.Analysis)

AnalysisManager.register("analysis.example.ExampleAnalysis")
AnalysisManager.register("analysis.domtree.DomTreeAnalysis")
