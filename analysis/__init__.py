"""
Analysis module
=================
Goldthorpe

This module manages which analyses are "registered" for use via amo.py
"""

import importlib
import analysis.tools

class _AnalysisManager:
    """
    Explicit manager of Analysis classes
    """
    def __init__(self):
        self._registered = dict()

    def register(self, analysis_name:str, alias:str=None):
        """
        Register an analysis (given by a path "Module.Submodule...Class" relative to .analysis)
        under the alias given by the string
        """
        components = analysis_name.split('.')
        module = '.'.join(components[:-1])
        cls_name = components[-1]
        if alias is None:
            alias = cls_name

        assert alias not in self._registered

        cls = getattr(importlib.import_module(module), cls_name)
        assert issubclass(cls, analysis.tools.Analysis)

        self._registered[alias] = cls

    def __contains__(self, alias):
        return alias in self._registered

    def __getitem__(self, alias):
        return self._registered[alias]

### Register analyses ###

AnalysisManager = _AnalysisManager()
AnalysisManager.register("analysis.example.ExampleAnalysis", "example")
