"""
Opt tools
===========
Goldthorpe

This module provides classes for reading and writing metadata
for analysing a CFG, as well as optimising the CFG
"""

import re
import functools

from ampy.ensuretypes import (
        Assertion,
        Syntax,
        TypedList,
        TypedDict,
        )
from ampy.passmanager import (
        BadArgumentException,
        Pass_ID_re,
        )
import ampy.debug
import ampy.types

class Opt:
    # forward declaration of getter/setter wrappers

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
        that everything after the CFG and list of existing opts are optional
        """
        cls.ID = ID
        def Opt_init_wrapper(initfunc):

            @functools.wraps(initfunc)
            @(Syntax(object, ampy.types.CFG, ((TypedList, [Opt]),), str, ...).set_allow_extra_kwargs(True, str) >> None)
            def Opt_init_wrap(self, cfg, opts, *args, **kwargs):
                args = list(args)
                if len(args) > len(def_args):
                    raise BadArgumentException(f"{cls.ID} expects at most {len(def_args)} positional argument{'s' if len(def_args) != 1 else ''}; received {len(args)}.")
                while len(args) < len(def_args):
                    args.append(def_args[len(args)])
                
                for kw in kwargs:
                    if kw not in def_kwargs:
                        raise BadArgumentException(f"Unrecognised keyword argument {kw} passed to {cls.ID}.")
                for kw in def_kwargs:
                    if kw not in kwargs:
                        kwargs[kw] = def_kwargs[kw]

                opts.append(self) # update opt list
                super().__init__(cfg, opts)

                self.debug(f"initialising opt with arguments {list(args)}, {dict(kwargs)}")
                initfunc(self, *args, **kwargs)
                self._inputs = (tuple(args), kwargs)

            Opt_init_wrap.__doc__ = ("Expects a CFG, a TypedList of previously-instantiated opts"
                        + (f", {len(def_args)} positional argument{'s' if len(def_args) != 1 else ''}" if len(def_args) > 0 else "")
                        + (f", and keyword argument{'s' if len(def_kwargs) != 1 else ''} {', '.join(def_kwargs.keys())}" if len(def_kwargs) > 0 else "")
                        + "."
                        + (f"\n{initfunc.__doc__}" if initfunc.__doc__ is not None else ""))

            return Opt_init_wrap

        return Opt_init_wrapper

    def getter(func):
        """
        Wrapper intended for subclass to identify methods
        that require opt to be valid.
        """
        @functools.wraps(func)
        def Opt_get_wrap(self, *args, **kwargs):
            if not self.valid:
                self._opt_pass()
            return func(self, *args, **kwargs)

        Opt_get_wrap.__doc__ = "Requires valid pass" + (f"\n{func.__doc__}" if func.__doc__ is not None else "")

        return Opt_get_wrap

    def setter(func):
        """
        Wrapper intended for subclass to identify methods
        that modify opt metadata (thus invalidating
        metadata and requiring recomputation)
        """
        @functools.wraps(func)
        def Opt_set_wrap(self, *args, **kwargs):
            self.valid = False
            return func(self, *args, **kwargs)

        Opt_set_wrap.__doc__ = "Invalidates previous pass" + (f"\n{func.__doc__}" if func.__doc__ is not None else "")

        return Opt_set_wrap


class RequiresOpt:
    """
    Provides functionality for querying opt data from opts handled
    by an Opt manager.
    """

    def __init__(self, cfg, opts):
        self.CFG = cfg
        self._opts = opts

    @property
    @(Syntax(object) >> [Opt])
    def opts(self):
        """
        Return the list of tracked opts
        """
        return self._opts

    @(Syntax(object, type, (str, type(any)), ...).set_allow_extra_kwargs(True, (str, type(any))) >> Opt)
    def require(self, opt_cls, *req_args, **req_kwargs):
        """
        Fetch data from a required opt with specified arguments.
        Set argument to `any` if it is unimportant.
        Unspecified or missing arguments are equivalent to passing `any`.
        """
        required = None
        for opt in self.opts:
            if not isinstance(opt, opt_cls):
                continue
            args, kwargs = opt.inputs
            if len(req_args) > len(args):
                continue
            if len(list(filter(lambda k: k not in kwargs, req_kwargs))) > 0:
                continue
            if not all(lha == rha or rha is any for lha, rha in zip(args, req_args)):
                continue
            if not all(kwargs[k] == req_kwargs[k] or req_kwargs[k] is any for k in req_kwargs):
                continue
            # at this point, everything matches up
            required = opt
            break

        if required is None:
            # opt cannot be found
            # so initalise a new opt
            # (this will also update opt list for next time)
            required = opt_cls(self.CFG, self.opts,
                    *(filter(lambda s: isinstance(s, str), req_args)),
                    **{key:arg for key, arg in req_kwargs.items() if isinstance(arg, str)})
            # "any" arguments are given default values

        return required


class Opt(Opt, RequiresOpt):
    """
    Parent class for manipulating metadata in a specific CFG

    Analyses are created by subclassing Opt.
    The __init__ method is required to be wrapped by @<subclass>.init(ID, ...)
    Arguments to __init__ (besides "self") are then arguments that will be
    expected in addition to the required CFG and list of existing opts, and
    default values for each argument are required to be passed to the wrapper.

    The ID of an opt must match the syntax for metadata arguments,
    EXCLUDING the character "/", which is necessary for the OptManager

    Validity of an Opt is tracked via CFG metadata
    """

    ### wrappers ###
    @classmethod
    @(Syntax(object, lambda:Syntax(object)>>[tuple, Opt])
     >> (lambda:Syntax(object)>>None))
    def opt_pass(cls, func):
        """
        Wrapper intended for subclass to identify its optimisation function.

        Wrapper also performs pre- and post-computations necessary for a
        uniform treatment of Opt objects (including safe invalidation
        of other opts).

        The return value of func is a collection of all opts that are
        explicitly "preserved" by the optimisation.
        """
        if hasattr(cls, "_opt_pass"):
            raise Exception("Optimisation can only have one opt method.")

        @functools.wraps(func)
        def Opt_pass_wrap(self):
            if self.valid:
                return
            self.debug(*self.inputs[0], *(f"{k}={v}" for k,v in self.inputs[1].items()), '$', "running optimisation")
            preserved = func(self)

            for opt in self.opts:
                if opt in preserved:
                    continue
                # anything not explicitly preserved is invalidated
                self.debug(f"invalidating {opt.ID} ({opt.inputs})")
                opt.valid = False

            self.valid = True

        Opt_pass_wrap.__doc__ = f"{cls.__name__} opt method" + (f"\n{func.__doc__}" if func.__doc__ is not None else "")
        cls._opt_pass = Opt_pass_wrap

        return Opt_pass_wrap

    ### methods ###

    def __init__(self):
        # this method should be overridden by subclass
        raise NotImplementedError

    @(Syntax(object, Opt) >> bool)
    def __eq__(self, other):
        return self.ID == other.ID and self.inputs == other.inputs
    
    @(Syntax(object) >> [set, ((), [tuple, str], {str:str})])
    def get_validated_inputs(self):
        """
        Checks the metadata to find all input parameter pairs passed to versions
        of the opt that have been validated.
        """
        meta = self.CFG.meta.get(self.ID, None)
        if meta is None:
            return set()
        index = 0
        outputs = set()
        while index < len(meta):
            args = []
            kwargs = TypedDict({}, str, str)
            while index < len(meta):
                if meta[index] == "$":
                    outputs.add((tuple(args), kwargs))
                    index += 1
                    break
                if '=' in meta[index]:
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
        Returns whether or not opt metadata is valid.
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
                self.debug("opt has been completely invalidated; clearing owned metadata")
                self.clear()
                del self.CFG.meta[self.ID]
            return

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
    @(Syntax(object, Pass_ID_re) >> None)
    def ID(cls, ID):
        cls._ID = ID
        cls._recog = re.compile(f"{cls._ID}/(.*)")

    @property
    @(Syntax(object) >> ((), [tuple, str], {str:str}))
    def inputs(self):
        return self._inputs

    @(Syntax(object, str) >> (str, None))
    def extract_arg(self, arg):
        """
        Takes a global metavariable and returns its component
        if owned by this opt
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
        with opt ID)
        """
        return f"{self.ID}/{arg}"

    @(Syntax(object, str) >> bool)
    def owns(self, arg):
        """
        Checks if metavariable is owned by opt
        """
        return arg.startswith(f"{self.ID}/")

    @(Syntax(object) >> None)
    def perform_opt(self):
        """
        Run opt
        
        Is implicitly called whenever arguments are fetched,
        but this can also be called explicitly

        NOT meant to be overridden; to implement an opt,
        use the @<subclass>.opt decorator
        """
        if not hasattr(type(self), "_opt_pass"):
            raise Exception("Opt needs an opt method.")
        
        self._opt_pass()

    @(Syntax(object) >> None)
    def clear(self):
        """
        Clear all metadata for this opt
        """
        for arg in tuple(self.CFG.meta):
            if self.owns(arg):
                del self.CFG.meta[arg]
        for block in self.CFG:
            for arg in tuple(block.meta):
                if self.owns(arg):
                    del block.meta[arg]
            for I in block:
                for arg in tuple(I.meta):
                    if self.owns(arg):
                        del I.meta[arg]

    @Opt.getter
    @(Syntax(object, str) # CFG #!var
      | Syntax(object, slice(ampy.types.BasicBlock, str)) # block @!var
      | Syntax(object, slice(ampy.types.BasicBlock, int, str)) # instr %!var
      >> ((list, [str]), None))
    def __getitem__(self, arg):
        if isinstance(arg, str):
            # CFG metadata
            return self.CFG.meta.get(self.tagged(arg), None)
        if isinstance(arg.stop, str):
            # block metadata
            return arg.start.meta.get(self.tagged(arg.stop), None)
        # instruction metadata
        return arg.start[arg.stop].meta.get(self.tagged(arg.step), None)

    @Opt.getter
    @(Syntax(object, str, default=((list, [str]), None)) # CFG #!var
      | Syntax(object, ampy.types.BasicBlock, str, default=((list, [str]), None)) # block @!var
      | Syntax(object, ampy.types.BasicBlock, int, str, default=((list, [str]), None)) # instr %!var
      >> ((list, [str]), None))
    def get(self, *args, default=None):
        """
        Get metavariable for CFG, block, or instruction
        If meta does is None, return default value
        """
        ret = (self[args[0]] if len(args) == 1 else
               self[args[0]:args[1]] if len(args) == 2 else
               self[args[0]:args[1]:args[2]])
        return default if ret is None else ret

    @Opt.setter
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

    def debug(self, *args, **kwargs):
        """
        Print debug information to ampy.debug
        """
        ampy.debug.print(self.ID, *args, **kwargs)

class OptList(TypedList):
    """
    Lazy type-checked list of opts
    """
    @(Syntax(object, ls=[Opt])
      | Syntax(object, [Opt])
      >> None)
    def __init__(self, ls=[]):
        super().__init__(ls, Opt)


class OptError(Exception):
    """
    Throw if opt discovers an error in the source code
    """
    def __init__(self, block:ampy.types.BasicBlock, index:int, message=""):
        self.block = block
        self.index = index
        self.message = message
        super().__init__(f"[{block.label}:{index}] {message}")

