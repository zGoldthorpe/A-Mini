"""
Analysis tools
================
Goldthorpe

This module provides classes for reading and writing metadata
for analysing a CFG
"""
#TODO: make metadata an ampy.ensuretypes.LazyDict type
#TODO: rename Lazy types as Typed types

import re
import functools

from ampy.ensuretypes import Syntax, Assertion
import ampy.debug
import ampy.types

_ID = r"[a-zA-Z0-9\-_.,;|]+"

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
        def wrap(self):
            if self.valid:
                return
            ampy.debug.print(type(self).__name__, "running analysis")
            func(self)
            self.valid = True
        
        wrap.__doc__ = f"{cls.__name__} analysis" + (f"\n{func.__doc__}" if func.__doc__ is not None else "")
        cls._analyser_method = wrap

        return wrap

    def get(func):
        """
        Wrapper intended for subclass to identify methods
        that require analysis to be valid.
        """
        @functools.wraps(func)
        def wrap(self, *args, **kwargs):
            if not self.valid:
                self._analyser_method()
            return func(self, *args, **kwargs)

        wrap.__doc__ = "Requires valid data" + (f"\n{func.__doc__}" if func.__doc__ is not None else "")

        return wrap

    def set(func):
        """
        Wrapper intended for subclass to identify methods
        that modify analysis metadata (thus invalidating
        metadata and requiring recomputation)
        """
        @functools.wraps(func)
        def wrap(self, *args, **kwargs):
            self.valid = False
            return func(self, *args, **kwargs)

        wrap.__doc__ = "Invalidates data" + (f"\n{func.__doc__}" if func.__doc__ is not None else "")

        return wrap

class Analysis(Analysis):
    """
    Parent class for manipulating metadata in a specific CFG

    Analyses are created by subclassing Analysis.
    The expectations of the __init__ method are:
    - has syntax matching Syntax(object, CFG) >> None
    - a field ID is defined
    - the CFG is stored in self.CFG
    The ID of an analysis must match the syntax for metadata arguments,
    EXCLUDING the character "/", which is necessary for the AnalysisManager

    Validity of an Analysis is tracked via CFG metadata
    """
    @(Syntax(object, ampy.types.CFG) >> None)
    def __init__(self, cfg):
        # this method should be overridden by subclass
        raise NotImplementedError

    @property
    @(Syntax(object) >> bool)
    def valid(self):
        """
        Returns whether or not analysis metadata is valid.
        (Manipulations to metadata outside of this class needs to invalidate
        its data explicitly.)
        """
        return self.CFG.meta.get(self.ID, None) is not None

    @valid.setter
    @(Syntax(object, bool) >> None)
    def valid(self, value):
        if value:
            self.CFG.meta[self.ID] = []
        elif self.valid:
            del self.CFG.meta[self.ID]

    @property
    @(Syntax(object) >> str)
    def ID(self):
        return self._ID

    @ID.setter
    @(Syntax(object, _ID) >> None)
    def ID(self, ID):
        self._ID = ID
        self._recog = re.compile(f"{self._ID}/(.*)")

    @(Syntax(object, str) >> (str, None))
    def extract_arg(self, arg):
        """
        Takes a global metavariable and returns its component
        if owned by this analysis
        (otherwise, returns None)
        """
        m = self._recog.fullmatch(arg)
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
