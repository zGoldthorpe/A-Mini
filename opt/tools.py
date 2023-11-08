"""
Optimisation tools
====================
Goldthorpe

This module provides classes for manipulating a program while
managing the validity of previous analyses.
"""

import functools

from ampy.ensuretypes import (
        Syntax,
        TypedList,
        )
from ampy.passmanager import (
        BadArgumentException,
        Pass_ID_re,
        )
import ampy.debug
import ampy.types

from analysis.tools import (
        Analysis,
        RequiresAnalysis,
        )

class Opt(RequiresAnalysis):
    # forward declaration
    # and define wrappers
    @classmethod
    @(Syntax(object, lambda:Syntax(object)>>[tuple, Analysis])
     >> (lambda:Syntax(object)>>None))
    def opt(cls, func):
        """
        Wrapper intended for subclass to identify its optimisation function.

        Wrapper also performs pre- and post-computations necessary for a
        uniform treatment of Opt objects (including safe invalidation
        of analyses).

        The return value of func is a collection of all analyses that are
        explicitly "preserved" by the optimisation.
        """
        if hasattr(cls, "_opt_method"):
            raise Exception("Optimisation can only have one opt method.")

        @functools.wraps(func)
        def Opt_opt_wrap(self):
            ampy.debug.print(self.ID, *self.inputs[0], *(f"{k}={v}" for k,v in self.inputs[1].items()), '$', "running optimisation")
            preserved = func(self)

            for analysis in self.analyses:
                if analysis in preserved:
                    continue
                # anything not explicitly preserved is invalidated
                ampy.debug.print(self.ID, f"invalidating {analysis.ID} ({analysis.inputs})")
                analysis.valid = False

        Opt_opt_wrap.__doc__ = f"{cls.__name__} opt method" + (f"\n{func.__doc__}" if func.__doc__ is not None else "")
        cls._opt_method = Opt_opt_wrap

        return Opt_opt_wrap
    
    @classmethod
    @Syntax(object, str, str, ...).set_allow_extra_kwargs(True, str)
    def init(cls, ID, *def_args, **def_kwargs):
        """
        Wrapper intended for subclass initialisation, with a specific ID.

        def_args
            default values for positional arguments
        def_kwargs
            default values for keyword arguments

        NB: this wrapper asserts correctness of arguments on the assumption
        that everything after the CFG and the list of analyses are optional
        """
        cls.ID = ID
        def Opt_init_wrapper(initfunc):

            @functools.wraps(initfunc)
            @(Syntax(object, ampy.types.CFG, ((TypedList, [Analysis]),), str, ...).set_allow_extra_kwargs(True, str) >> None)
            def Opt_init_wrap(self, cfg, analyses, *args, **kwargs):
                args = list(args)
                if len(args) > len(def_args):
                    raise BadArgumentException(f"{cls.ID} optimisation expects at most {len(def_args)} positional argument{'s' if len(def_args) != 1 else ''}; received {len(args)}.")
                while len(args) < len(def_args):
                    args.append(def_args[len(args)])

                for kw in kwargs:
                    if kw not in def_kwargs:
                        raise BadArgumentException(f"Unrecognised keyword argument {kw} passed to {cls.ID} optimisation.")
                for kw in def_kwargs:
                    if kw not in kwargs:
                        kwargs[kw] = def_kwargs[kw]

                super().__init__(cfg, analyses)

                ampy.debug.print(ID, f"Initialising optimisation with arguments {args}, {kwargs}")
                initfunc(self, *args, **kwargs)
                self._inputs = (tuple(args), kwargs)

            Opt_init_wrap.__doc__ = ("Expects a CFG, a TypedList of analysis"
                        + (f", {len(def_args)} positional argument{'s' if len(def_args) != 1 else ''}" if len(def_args) > 0 else "")
                        + (f", and keyword argument{'s' if len(def_kwargs) != 1 else ''} {', '.join(def_kwargs.keys())}" if len(def_kwargs) > 0 else "")
                        + "."
                        + (f"\n{initfunc.__doc__}" if initfunc.__doc__ is not None else ""))

            return Opt_init_wrap

        return Opt_init_wrapper


class Opt(Opt):
    """
    Parent class for optimising a CFG

    Optimisations are created by subclassing Opt.
    The __init__ method is required to be wrapped by @<subclass>.init(ID, ...)
    Arguments to __init__ (besides "self") are then arguments that will be
    expected in addition to the required CFG and list of analyses, and
    default values for each argument are required to be passed to the wrapper.
    """
    
    def __init__(self):
        # this method must be overridden by subclass
        raise NotImplementedError

    @property
    @classmethod
    @(Syntax(object) >> str)
    def ID(self):
        return self._ID

    @ID.setter
    @classmethod
    @(Syntax(object, Pass_ID_re) >> None)
    def ID(self, ID):
        self._ID = ID

    @property
    @(Syntax(object) >> ((), [tuple, str], {str:str}))
    def inputs(self):
        return self._inputs

    @(Syntax(object) >> None)
    def perform_opt(self):
        """
        Run optimisation

        NOT meant to be overridden; to implement an optimisation,
        use the @<subclass>.opt decorator
        """
        if not hasattr(type(self), "_opt_method"):
            raise Exception("Optimisation needs an opt method.")

        self._opt_method()

    @(Syntax(object, int)
      | Syntax(object, int, r"@?[.\w]+")
      >> [str])
    def gen_labels(self, count, prefix=None, /):
        """
        Generate available block labels.
        If prefix not set, label is prefixed with the optimisation ID.
        """
        counter = 0
        prefix = self.ID if prefix is None else f"{prefix}." if len(prefix) > 0 else ""
        if not prefix.startswith('@'):
            prefix = '@' + prefix

        labels = self.CFG.labels
        out = []

        while len(out) < count:
            label = prefix + str(counter)
            if label not in labels:
                out.append(label)
            counter += 1

        return out

    @(Syntax(object)
      | Syntax(object, r"@?[.\w]+")
      >> str)
    def gen_label(self, prefix=None, /):
        return self.gen_labels(1, prefix)[0]
