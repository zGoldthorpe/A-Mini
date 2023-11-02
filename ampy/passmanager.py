"""
Pass Manager
==============
Goldthorpe

This module provides the class used for managing passes
(analysis, optimisation, etc.)
"""

import importlib

from ampy.ensuretypes import (
        Assertion,
        Syntax,
        TypedDict,
        )

class PassManager:
    """
    Pass manager

    Register classes from various modules under aliases, and access
    the classes using these aliases.
    """

    @(Syntax(object, type) >> None)
    def __init__(self, classtype):
        """
        classtype is the type that all registered classes must subtype
        """
        self._classtype = classtype
        self._registered = TypedDict(dict(), str, ((type, Assertion(lambda cls:issubclass(cls, self._classtype))),))

    @(Syntax(object, str, (str, None))
      | Syntax(object, str, alias=(str,None))
      >> None)
    def register(self, cls_path, alias=None):
        """
        Register a class (given by cls_path "Module.Submodule...Class"
        relative to '.') under the specified alias, if provided.
        """
        components = cls_path.split('.')
        module = '.'.join(components[:-1])
        cls_name = components[-1]
        if alias is None:
            alias = cls_name

        assert alias not in self._registered # aliases must be unique

        cls = getattr(importlib.import_module(module), cls_name)

        self._registered[alias] = cls

    @(Syntax(object) >> {str})
    def __iter__(self):
        for alias in self._registered:
            yield alias

    @(Syntax(object, str) >> bool)
    def __contains__(self, alias):
        return alias in self._registered

    @(Syntax(object, str) >> type)
    def __getitem__(self, alias):
        return self._registered[alias]
