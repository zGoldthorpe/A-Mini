"""
Analysis tools
================
Goldthorpe

This module provides classes for reading and writing metadata
for analysing a CFG
"""

import re
import functools

from ampy.ensuretypes import (
        Assertion,
        Syntax,
        TypedList,
        TypedDict,
        )
from ampy.passmanager import BadArgumentException
import ampy.debug
import ampy.types

ID_re = r"[a-zA-Z0-9\-_.,;|]+"

class Analysis:
    # forward declaration
    # also defines wrappers
    @classmethod
    def analysis(cls, func):
        """
        Wrapper intended for subclass to identify its
        analysis function.

        Wrapper also performs pre- and post-computations
        necessary for a uniform treatment of Analysis objects
        """
        if hasattr(cls, "_analyser_method"):
            raise Exception("Analysis can only have one analysis method.")

        @functools.wraps(func)
        def Analysis_analysis_wrap(self):
            if self.valid:
                return
            ampy.debug.print(type(self).__name__, "running analysis")
            func(self)
            self.valid = True
        
        Analysis_analysis_wrap.__doc__ = f"{cls.__name__} analysis" + (f"\n{func.__doc__}" if func.__doc__ is not None else "")
        cls._analyser_method = Analysis_analysis_wrap

        return Analysis_analysis_wrap

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
        that everything after the CFG and list of existing analyses are optional
        """
        cls.ID = ID
        def Analysis_init_wrapper(initfunc):

            @functools.wraps(initfunc)
            @(Syntax(object, ampy.types.CFG, ((TypedList, [Analysis]),), str, ...).set_allow_extra_kwargs(True, str) >> None)
            def Analysis_init_wrap(self, cfg, analyses, *args, **kwargs):
                self.CFG = cfg
                args = list(args)
                if len(args) > len(def_args):
                    raise BadArgumentException(f"{cls.__name__} expects at most {len(def_args)} positional arguments; receive {len(args)}.")
                while len(args) < len(def_args):
                    args.append(def_args[len(args)])
                
                for kw in kwargs:
                    if kw not in def_kwargs:
                        raise BadArgumentException(f"Unrecognised keyword argument {kw} passed to {cls.__name__}")
                for kw in def_kwargs:
                    if kw not in kwargs:
                        kwargs[kw] = def_kwargs[kw]

                self._analyses = analyses
                self._analyses.append(self)
                initfunc(self, *args, **kwargs)
                self._inputs = (tuple(args), kwargs)

            Analysis_init_wrap.__doc__ = ("Expects a CFG, a TypedList of previously-instantiated analyses"
                        + (f", {len(def_args)} positional argument{'s' if len(def_args) != 1 else ''}" if len(def_args) > 0 else "")
                        + (f", and keyword argument{'s' if len(def_kwargs) > 0 else ''} {', '.join(def_kwargs.keys())}" if len(def_kwargs) > 0 else "")
                        + "."
                        + (f"\n{initfunc.__doc__}" if initfunc.__doc__ is not None else ""))

            return Analysis_init_wrap

        return Analysis_init_wrapper

    def get(func):
        """
        Wrapper intended for subclass to identify methods
        that require analysis to be valid.
        """
        @functools.wraps(func)
        def Analysis_get_wrap(self, *args, **kwargs):
            if not self.valid:
                self._analyser_method()
            return func(self, *args, **kwargs)

        Analysis_get_wrap.__doc__ = "Requires valid data" + (f"\n{func.__doc__}" if func.__doc__ is not None else "")

        return Analysis_get_wrap

    def set(func):
        """
        Wrapper intended for subclass to identify methods
        that modify analysis metadata (thus invalidating
        metadata and requiring recomputation)
        """
        @functools.wraps(func)
        def Analysis_set_wrap(self, *args, **kwargs):
            self.valid = False
            return func(self, *args, **kwargs)

        Analysis_set_wrap.__doc__ = "Invalidates data" + (f"\n{func.__doc__}" if func.__doc__ is not None else "")

        return Analysis_set_wrap

class Analysis(Analysis):
    """
    Parent class for manipulating metadata in a specific CFG

    Analyses are created by subclassing Analysis.
    The __init__ method is required to be wrapped by Subclass.init(ID)
    Arguments to __init__ (besides "self") are then arguments that will be
    expected in addition to the required CFG and list of existing analyses.

    The ID of an analysis must match the syntax for metadata arguments,
    EXCLUDING the character "/", which is necessary for the AnalysisManager

    Validity of an Analysis is tracked via CFG metadata
    """
    @(Syntax(object, ampy.types.CFG, [Analysis]) >> None)
    def __init__(self, cfg, analyses):
        # this method should be overridden by subclass
        raise NotImplementedError
    
    @(Syntax(object) >> [set, ([[tuple, str], {str:str}],)])
    def get_validated_inputs(self):
        """
        Checks the metadata to find all input parameter pairs passed to versions
        of the analysis that have been validated.
        """
        meta = self.CFG.meta.get(self.ID, None)
        if meta is None:
            return []
        index = 0
        outputs = set()
        while index < len(meta):
            args = []
            kwargs = TypedDict({}, str, str)
            while index < len(meta):
                if meta[index] == "$":
                    outputs.add((tuple(args), kwargs))
                elif '=' in meta[index]:
                    key, val = map(lambda s:s.strip(), meta[index].split('=', 1))
                    kwargs[key] = val
                else:
                    args.append(meta[index])
                index += 1
        return outputs

    @property
    @(Syntax(object) >> bool)
    def valid(self):
        """
        Returns whether or not analysis metadata is valid.
        (Manipulations to metadata outside of this class needs to invalidate
        its data explicitly.)
        """
        return self.inputs in self.get_validated_inputs()

    @valid.setter
    @(Syntax(object, bool) >> None)
    def valid(self, value):
        validated = self.get_validated_inputs()
        if value:
            validated.add(self.inputs)
        elif self.valid:
            validated.remove(self.inputs)
        
        # we might have completely invalidated the pass
        if len(validated) == 0:
            if self.valid:
                del self.CFG.meta[self.ID]

        # now store the updated validity list
        validated_list = []
        for args, kwargs in validated:
            for arg in args:
                validated_list.append(arg)
            for kw, arg in kwargs.items():
                validated_list.append(f"{kw}={arg}")
            validated_list.append("$")
        self.CFG.meta[self.ID] = validated_list

    @property
    @classmethod
    @(Syntax(object) >> str)
    def ID(cls):
        return cls._ID

    @ID.setter
    @classmethod
    @(Syntax(object, ID_re) >> None)
    def ID(cls, ID):
        cls._ID = ID

    @property
    @(Syntax(object) >> ([[tuple, str], {str:str}],))
    def inputs(self):
        return self._inputs

    @property
    @(Syntax(object) >> [Analysis])
    def analyses(self):
        return self._analyses

    @(Syntax(object, str) >> (str, None))
    def extract_arg(self, arg):
        """
        Takes a global metavariable and returns its component
        if owned by this analysis
        (otherwise, returns None)
        """
        m = cls._recog.fullmatch(arg)
        if m is None:
            return None
        return m.group(1)

    @(Syntax(object, str) >> str)
    def tagged(self, arg):
        """
        Makes owned variable a global metavariable (i.e., prefixed
        with analysis ID)
        """
        return f"{self.ID}/{arg}"

    @(Syntax(object) >> None)
    def perform_analysis(self):
        """
        Run analysis
        
        Is implicitly called whenever arguments are fetched,
        but this can also be called explicitly

        NOT meant to be overridden: to implement an analysis,
        use the @<subclass>.analysis decorator
        """
        if not hasattr(type(self), "_analyser_method"):
            raise Exception("Analysis needs an analysis method.")
        
        self._analyser_method()

    @(Syntax(object) >> None)
    def clear(self):
        """
        Clear all metadata for this analysis
        """
        for block in self._cfg:
            for I in block:
                for arg in I.meta:
                    if self.owns(arg):
                        del I.meta[arg]

    @Analysis.get
    @(Syntax(object, str) # CFG #!var
      | Syntax(object, slice(ampy.types.BasicBlock, str)) # block @!var
      | Syntax(object, slice(ampy.types.BasicBlock, int, str)) # instr %!var
      >> ((list, [str]), None))
    def __getitem__(self, arg):
        if isinstance(arg, str):
            # CFG metadata
            return self.CFG.meta.get(self.tagged(arg), default=None)
        if isinstance(arg.stop, str):
            # block metadata
            return arg.start.meta.get(self.tagged(arg.stop), default=None)
        # instruction metadata
        return arg.start[arg.stop].meta.get(self.tagged(arg.step), default=None)

    @Analysis.set
    @(Syntax(object, str, str, ..., append=bool) # CFG #!var
     | Syntax(object, ampy.types.BasicBlock, str, str, ..., append=bool) # block @!var
     | Syntax(object, ampy.types.BasicBlock, int, str, str, ..., append=bool) # instr %!var
     >> None)
    def assign(self, *vv, append=False):
        """
        assign(CFGkey, values ...)
        assign(BB, BBkey, values ...)
        assign(BB, idx, instr_key, values ...)

        Assign a metavariable argument to a specific value.
        The append kwarg toggles if the assigned variable is appended to
        existing values, or clears the existing list
        """
        if len(vv) > 1 and isinstance(vv[1], int):
            # instruction
            meta = vv[0][vv[1]].meta
            arg = vv[2]
            vals = vv[3:]
        elif len(vv) > 0 and isinstance(vv[0], ampy.types.BasicBlock):
            # block
            meta = vv[0].meta
            arg = vv[1]
            vals = vv[2:]
        else:
            # CFG
            meta = self.CFG.meta
            arg = vv[0]
            vals = vv[1:]
        
        if append:
            meta.setdefault(self.tagged(arg), []).extend(vals)
        else:
            meta[self.tagged(arg)] = list(vals)

class AnalysisList(TypedList):
    """
    Lazy type-checked list of analyses
    """
    @(Syntax(object, ls=[Analysis])
      | Syntax(object, [Analysis])
      >> None)
    def __init__(self, ls=[]):
        super().__init__(ls, Analysis)
