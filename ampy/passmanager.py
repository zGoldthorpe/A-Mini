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

Pass_ID_re = r"[a-zA-Z0-9\-_.,;|]+"

global_registry = set()

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
    def register(self, cls_path, ID="ID"):
        """
        Register a class (given by cls_path "Module.Submodule...Class"
        relative to '.'), with alias given by the ID field
        """
        components = cls_path.split('.')
        module = '.'.join(components[:-1])
        cls_name = components[-1]
        
        cls = getattr(importlib.import_module(module), cls_name)
        alias = getattr(cls, ID)
        if isinstance(alias, property):
            # in case ID is not a variable but a getter method
            alias = alias.fget(cls)

        if alias in global_registry:
            raise NameError(f"Alias {alias} already registered.")
        assert alias not in global_registry # aliases must be unique

        self._registered[alias] = cls
        global_registry.add(alias)

    @(Syntax(object) >> [iter, str])
    def __iter__(self):
        for alias in self._registered:
            yield alias

    @(Syntax(object, str) >> bool)
    def __contains__(self, alias):
        return alias in self._registered

    @(Syntax(object, str) >> type)
    def __getitem__(self, alias):
        return self._registered[alias]

class BadArgumentException(Exception):
    """
    Exception specific to passes being given unexpected
    or incorrect arguments.
    """

    def __init__(self, message=""):
        self.message = message
        super().__init__(self.message)
