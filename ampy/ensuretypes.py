"""
EnsureTypes
=============
Goldthorpe

This module provides wrapper classes for type-assertions for methods.
Non-primitive types are asserted lazily (e.g., if an object must be an iterable
consisting of 10 integers, then the entries will be asserted to be integers as
they are used by the callee function).
"""
import functools
from types import (
        EllipsisType,
        FunctionType,
        )

class Syntax:
    # forward declaration
    pass

class Syntax(Syntax):
    """
    Syntax object

    Checks positional and keyword argument types.

    (type0, type1, type2 [, ...])
        Match any of the above types
        Each typeN should be a primitive type (Syntax does lazy type-checking, so
        will incorrectly match types if typeN is more elaborate, and then assert
        that typeN matches this constructed type).
        If more elaborate types are needed, replace typeN with a pair (hintN, consN)
        where hintN is a primitive type for quick matching, and consN is the more
        precise match (which is then asserted to whatever matches hintN).
        
        E.g., Syntax((int, (list, [int, 5]), (dict, {str:str}))) expects one
        argument, whose type is one of:
        - int
        - list (after which is asserted to be a list of 5 integers)
        - dict (after which is asserted to be a map from strings to strings)

    [container, type, [lo, hi]]
        Type must be a container-like iterable of entries of specified
        type, where the number of entries is bounded between lo and hi,
        inclusive.
        Use ellipses for lo or hi to indicate unboundedness in either
        direction.

        [*, type, N] is shorthand for [*, type, [N, N]]
        [*, type] is shorthand for [*, type, ...] = [*, type, [...,...]]
        [type, *] is shorthand for [list, type, *]

    {type0 : type1}
        Type must be a dict from type0 to type1

    {type}
        Type must be a generator of indicated type

    lambda : Syntax(*args, **kwargs) >> type
        Type must be a function with specified syntax

    None
        Alias for NoneType

    type, ...
        If type is a positional argument, then the ellipses act as a Kleene star
        for this type; i.e., match zero or more of this type as positional arguments.

    kwarg=type
        If function takes keyword argument kwarg, then kwarg must have specified type.

    .set_allow_undef_kwargs(flag):
        toggle if function calls with missing kwargs are permissible
        (default: True)
    
    .set_allow_extra_kwargs(flag):
        toggle if function calls with unanticipated kwargs are permissible
        (default: False)

    .union(*args, **kwargs)
    | Syntax(*args, **kwargs)
        match either current syntax object or next syntax object
        NB: piped syntax objects do not inherit above flags
        NB: matches can only be checked for elementary types (i.e.,
            NOT for [type, N] or {ty0:ty1}, or {type})

    .returns(type)
    >> type
        asserts and checks return type
        (default: object -- any return type is valid)
        NB: only final Syntax object of pipe string needs return type specified
    """
    
    def _verify_input(ty):
        """
        Ensures that type arguments of Syntax initialisation are
        comprehensible, making adjustments to the more elaborate
        types

        Returns True or throws a SyntaxError

        Does not handle ellipses; handle these externally
        """
        if ty is None:
            # NoneType
            return True

        if isinstance(ty, type):
            # primitive type
            return True

        if isinstance(ty, tuple):
            # union
            for t in ty:
                if t is None:
                    continue
                if isinstance(t, type):
                    continue # primitive type
                if not isinstance(t, tuple) or len(t) != 2 or not isinstance(t[0], type):
                    raise SyntaxError("Union type must consist of primitive types or (primitive, cons) pairs")
                # (hint, type) pair
                Syntax._verify_input(t[1])
            return True

        if isinstance(ty, list):
            # iterable of fixed element type
            errmsg = "Iterable type must be of the form [container, type, count]"
            containers = (list, set, tuple, str)

            # unpack shorthands
            match len(ty):
                case 1: # [type] = [list, type, ...]
                    ty.insert(0, list)
                    ty.append(Ellipsis)
                case 2: # [container, type] or [type, count]
                    if isinstance(ty[1], (int, EllipsisType, list)):
                        # [type, count] = [list, type, count]
                        ty.insert(0, list)
                    else:
                        # [container, type] = [container, type, ...]
                        ty.append(Ellipsis)
                case 3:
                    pass
                case _: # invalid
                    raise SyntaxError(errmsg)

            # now, ty = [container, type, counter]
            if not ty[0] in containers:
                raise SyntaxError(errmsg + " where the container is one of: " + ", ".join(t.__name__ for t in containers))
            if not isinstance(ty[2], list):
                if not isinstance(ty[2], (int, EllipsisType)):
                    raise SyntaxError(errmsg + " where the count is an integer, ellipses, or a [lo, hi] pair of such")
                # [*,*, N] = [*,*, [N, N]]
                ty[2] = [ty[2], ty[2]]

            # now, counter is a list
            if len(ty[2]) != 2 or not all(isinstance(t, (int, EllipsisType)) for t in ty[2]):
                raise SyntaxError(errmsg + " where the count is an integer, ellipses, or a [lo, hi] pair of such")

            # now, ty = [container, type, [lo, hi]]
            return Syntax._verify_input(ty[1])

        if isinstance(ty, set):
            # iterator of fixed type
            if len(ty) != 1:
                raise SyntaxError("Iterator type must be of the form {type}")
            gty = list(ty)[0]
            return Syntax._verify_input(gty)

        if isinstance(ty, dict):
            # dictionary of fixed key-value type pairing
            if len(ty) != 1:
                raise SyntaxError("Dict type must be of the form {ktype : vtype}")
            kty = list(ty)[0]
            return Syntax._verify_input(kty) and Syntax._verify_input(ty[kty])

        if isinstance(ty, FunctionType):
            # function must have zero arity
            errmsg = "Function type must be of the form lambda:Syntax(*args, **kwargs)."
            try:
                syntax = ty()
            except TypeError:
                raise SyntaxError(errmsg + " Lambda has nonzero arity.")
            if not isinstance(syntax, Syntax):
                raise SyntaxError(errmsg + " Lambda does not return Syntax object")
            return True

        # input type does not match any of the above syntax
        raise SyntaxError(f"Unrecognised type {repr(ty)}")

    def __init__(self, *types, **kwtypes):
        self._types = tuple(filter(lambda t: t is not Ellipsis, types))
        # verify syntax arguments
        pretypes = []
        self._parent = None # parent syntax, in case of chaining
        self._ellipsis = -1
        for i, ty in enumerate(types):
            if ty is Ellipsis:
                if i == 0:
                    raise SyntaxError("Syntax cannot begin with ellipses")
                if self._ellipsis > -1:
                    raise SyntaxError("Syntax cannot have multiple instances of ellipses in positional argument")
                self._ellipsis = i - 1
                continue
            if Syntax._verify_input(ty):
                pretypes.append(ty)
        self._types = tuple(pretypes)
        
        self._kwtypes = dict()
        for kw in kwtypes:
            if Syntax._verify_input(kwtypes[kw]):
                self._kwtypes[kw] = kwtypes[kw]

        # other flags / etc. set to default
        self._allow_undef_kwargs = True
        self._allow_extra_kwargs = False
        self._return_type = object

    def _type_name(ty):
        """
        Presents abstract Syntax types in a readable fashion
        """
        if ty is None:
            return "None"

        if ty is Ellipsis:
            return "..."

        if isinstance(ty, type):
            return ty.__name__

        if isinstance(ty, tuple):
            union = ", ".join("None" if t is None
                    else t.__name__ if isinstance(t, type)
                    else f"( {t[0].__name__} , {Syntax._type_name(t[1])} )"
                    for t in ty)
            return f"( {union}, )"

        if isinstance(ty, list):
            ty0 = ty[0].__name__
            ty1 = Syntax._type_name(ty[1])
            lo, hi = map(lambda t: "..." if t is Ellipsis else t, ty[2])
            return f"[ {ty0}, {ty1}, [ {lo}, {hi} ] ]"

        if isinstance(ty, set):
            gty = list(ty)[0]
            return f"{{ {Syntax._type_name(gty)} }}"

        if isinstance(ty, dict):
            kty = list(ty)[0]
            vty = ty[kty]
            return f"{{ {Syntax._type_name(kty)} : {Syntax._type_name(vty)} }}"

        if isinstance(ty, FunctionType):
            syntax = ty()
            return f"lambda : {repr(syntax)}"

    def extract_syntax(*args, **kwargs):
        """
        Infers simplest Syntax object that would accept the
        given *args, **kwargs pair for a function call
        """
        return Syntax(*[type(arg) for arg in args], **{kw:type(kwargs[kw]) for kw in kwargs})

    def set_allow_undef_kwargs(self, flag):
        """
        Toggle whether Syntax permits (if True) missing kwargs in
        function call that have a type assertion provided to the
        Syntax instance
        """
        self._allow_undef_kwargs = flag
        return self # allow for chaining modifiers after constructor
    
    def set_allow_extra_kwargs(self, flag):
        """
        Toggle whether Syntax permits (if True) arguments passed
        to the function that do not have a type assertion provided
        to the Syntax instance
        """
        self._allow_extra_kwargs = flag
        return self

    def __rshift__(self, ty):
        """
        Set return type of Syntax
        """
        Syntax._verify_input(ty)
        self._return_type = ty
        if self._parent is not None:
            self._parent.__rshift__(ty)
        return self

    def returns(self, ty):
        """
        Equivalent to self >> ty
        """
        return self.__rshift__(ty)

    def __or__(self, other:Syntax):
        """
        Union current Syntax with another.
        Type-checking must satisfy one of these.
        """
        other._parent = self
        return other

    def union(self, *args, **kwargs):
        """
        Equivalent to self | Syntax(*args, **kwargs)
        """
        return self.__or__(Syntax(*args, **kwargs))

    @property
    def _syntaxes(self):
        if self._parent is not None:
            for syntax in self._parent._syntaxes:
                yield syntax
        yield repr(self)

    def _check_wrap(arg, ty, errmsg=""):
        """
        Lazily check if arg is of type ty, given conventions of the
        Syntax class
        """
        if ty is None:
            if arg is None:
                return arg

        if isinstance(ty, type):
            if isinstance(arg, ty):
                return arg

        if isinstance(ty, tuple):
            for t in ty:
                if t is None:
                    if arg is None:
                        return arg
                if isinstance(t, type):
                    if isinstance(arg, t):
                        return arg
                else:
                    mty, cons = t
                    if isinstance(arg, mty):
                        # primitive match, so assert elaborate type "cons"
                        return Syntax._check_wrap(arg, cons, errmsg=errmsg)

        if isinstance(ty, list):
            if hasattr(arg, "__iter__"):
                lo, hi = ty[2]
                lo = 0 if lo is Ellipsis else lo
                hi = len(arg) if hi is Ellipsis else hi
                if lo <= len(arg) <= hi:
                    if ty[0] == list:
                        return LazySyntaxList(arg, ty[1], errmsg=errmsg)
                    if ty[0] == set:
                        return LazySyntaxSet(arg, ty[1], errmsg=errmsg)
                    if ty[0] == tuple:
                        return LazySyntaxTuple(arg, ty[1], errmsg=errmsg)
                    if ty[0] == str:
                        return LazySyntaxString(arg, ty[1], errmsg=errmsg)

        if isinstance(ty, set):
            gty = list(ty)[0]
            if hasattr(arg, "__next__"):
                return LazySyntaxIterator(arg, gty, errmsg=errmsg)
                
        if isinstance(ty, dict):
            kty = list(ty)[0]
            vty = ty[kty]
            if hasattr(arg, "__iter__") and hasattr(arg, "__getitem__"):
                return LazySyntaxDict(arg, kty, vty, errmsg=errmsg)

        if isinstance(ty, FunctionType):
            syntax = ty()
            if isinstance(arg, FunctionType):
                return syntax(arg)

        # at this point, arg failed typecheck
        raise TypeError(errmsg)

    def check(self, func_name, *args, **kwargs):
        """
        Assert correctness of args and kwargs passed to function,
        or at least lazily propagate these assertions for when the
        argument gets used.

        Returns modified versions of the args and kwargs to
        actually get passed to the function
        """
        arg_diff = len(args) - len(self._types) + 1
        if self._ellipsis > -1:
            types = (self._types[:self._ellipsis]
                    + (self._types[self._ellipsis],) * arg_diff
                    + self._types[self._ellipsis+1:])
        else:
            types = self._types
        if len(args) != len(types):
            raise TypeError(f"{func_name} expects {len(self._types)} positional arguments; {len(args)} given.")
        wrapped_args = map(lambda P:
                Syntax._check_wrap(
                    arg=P[1][0], # arg
                    ty=P[1][1], # type
                    errmsg=f"{func_name} argument {P[0]} expects {Syntax._type_name(P[1][1])}; unexpected {type(P[1][0]).__name__} given."),
                enumerate(zip(args, types)))
        wrapped_kwargs = dict()
        for kw in kwargs:
            if kw not in self._kwtypes:
                if self._allow_extra_kwargs:
                    continue
                raise TypeError(f"{func_name} received unexpected keyword argument {kw}.")
            wrapped_kwargs[kw] = Syntax._check_wrap(
                        arg=kwargs[kw],
                        ty=self._kwtypes[kw],
                        errmsg=f"{func_name} keyword argument {kw} expects {Syntax._type_name(self._kwtypes[kw])}; unexpected {Syntax._type_name(type(kwargs[kw]))} given.")
        if not self._allow_undef_kwargs:
            for kw in self._kwtypes:
                if kw not in kwargs:
                    raise TypeError(f"{func_name} missing expected keyword {kw}.")

        return wrapped_args, wrapped_kwargs

    def check_iter(self, func_name, syntax_list, *args, **kwargs):
        """
        If Syntax is part of a union, recursively check all instances
        in the union and find the first match (in reverse order of
        instantiation).

        Returns args and kwargs modified according to the first ancestor
        to (lazily) accept the arguments.
        """
        syntax_list.append(repr(self))
        try:
            args, kwargs = self.check(func_name, *args, **kwargs)
            args = tuple(args) # force type check
        except Exception as e:
            if self._parent is None:
                raise TypeError(f"""{func_name} received unrecognised argument pattern
\t{repr(Syntax.extract_syntax(*args, **kwargs))}
Valid syntaxes are:
\t{(chr(10)+chr(9)).join(syntax for syntax in reversed(syntax_list))}""")

            args, kwargs = self._parent.check_iter(func_name, syntax_list, *args, **kwargs)
        return args, kwargs

    def __repr__(self):
        if self._parent is not None:
            head = self._parent.__repr__() + '\n'
        else:
            head = ""

        if self._return_type is object:
            # I thought to suppress notation of return is NoneType
            # but the default return type is "object"
            tail = ""
        else:
            tail = f" >> {Syntax._type_name(self._return_type)}"

        positional_ty = list(self._types)
        if self._ellipsis > -1:
            positional_ty.insert(self._ellipsis+1, Ellipsis)
        positional = ", ".join(Syntax._type_name(ty) for ty in positional_ty)
        keyword = ", ".join(f"{kw}:{Syntax._type_name(self._kwtypes[kw])}" for kw in self._kwtypes)
        if not positional and not keyword:
            return head + "Syntax()" + tail
        if not positional:
            return head + f"Syntax({keyword})" + tail
        if not keyword:
            return head + f"Syntax({positional})" + tail
        return head + f"Syntax({positional}; {keyword})" + tail

    def __call__(self, func):
        """
        Wrapper for type assertions
        """
        @functools.wraps(func)
        def wrap(*args, **kwargs):
            if self._parent is None:
                args, kwargs = self.check(func.__name__, *args, **kwargs)
            else:
                args, kwargs = self.check_iter(func.__name__, [], *args, **kwargs)
            retval = func(*args, **kwargs)
            return Syntax._check_wrap(
                    arg=retval,
                    ty=self._return_type,
                    errmsg=f"{func.__name__} expected to return {Syntax._type_name(self._return_type)}; returned unexpected {type(retval).__name__}.")

        wrap.__doc__ = repr(self) + (f"\n{func.__doc__}" if func.__doc__ is not None else "")

        return wrap


class LazySyntaxList(list):
    """
    Lazy type-checker for list-like iterable

    Implementation is also lazy; it's easy to cheat this checker,
    but that's deviating from the point of the ensuretypes module
    (which is just designed to keep myself honest).
    """
    def __init__(self, ls, ty, errmsg=""):
        self._ty = ty
        self._errmsg = errmsg
        super().__init__(ls)

    def __repr__(self):
        return f"{super().__repr__()}:{Syntax._type_name(self._ty)}"
    
    def __iter__(self):
        return Syntax._check_wrap(
                arg=super().__iter__(),
                ty={self._ty}, # iterator
                errmsg=self._errmsg)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return Syntax._check_wrap(
                    arg=super().__getitem__(index),
                    ty=[self._ty, ..., list],
                    errmsg=self._errmsg)
        return Syntax._check_wrap(
                arg=super().__getitem__(index),
                ty=self._ty,
                errmsg=self._errmsg + f" Index {index} has incorrect type.")

    def __setitem__(self, index, value):
        super().__setitem__(index, Syntax._check_wrap(
                arg=value,
                ty=self._ty,
                errmsg=self._errmsg + f" Assigning incorrect type to index {index}."))

class LazySyntaxSet(set):
    """
    Lazy type-checker for set-like iterable
    """
    def __new__(cls, st, ty, errmsg=""):
        return super().__new__(cls)

    def __init__(self, st, ty, errmsg=""):
        self._ty = ty
        self._errmsg = errmsg
        super().__init__(st)

    def __repr__(self):
        return f"{repr(set(self))}:{Syntax._type_name(self._ty)}"
    
    def __iter__(self):
        return Syntax._check_wrap(
                arg=super().__iter__(),
                ty={self._ty}, # iterator
                errmsg=self._errmsg)

    def pop(self):
        return Syntax._check_wrap(
                arg=super().pop(),
                ty=self._ty,
                errmsg=self._errmsg + " Set poppsed incorrect type.")

    def add(self, item):
        super().add(Syntax._check_wrap(
                arg=item,
                ty=self._ty,
                errmsg=self._errmsg + " Trying to add incorrect type."))

class LazySyntaxTuple(tuple):
    """
    Lazy type-checker for tuple-like iterable
    """
    def __new__(cls, tp, ty, errmsg=""):
        # tuple is immutable
        return super().__new__(cls, tp)

    def __init__(self, tp, ty, errmsg=""):
        self._ty = ty
        self._errmsg = errmsg
    
    def __iter__(self):
        return Syntax._check_wrap(
                arg=super().__iter__(),
                ty={self._ty}, # iterator
                errmsg=self._errmsg)

    def __repr__(self):
        return f"{super().__repr__()}:{Syntax._type_name(self._ty)}"

    def __getitem__(self, index):
        if isinstance(index, slice):
            return Syntax._check_wrap(
                    arg=super().__getitem__(index),
                    ty=[self._ty, ..., tuple],
                    errmsg=self._errmsg)
        return Syntax._check_wrap(
                arg=super().__getitem__(index),
                ty=self._ty,
                errmsg=self._errmsg + f" Index {index} has incorrect type.")

class LazySyntaxString(str):
    """
    Lazy type-checker for string-like iterable

    Implementation is also lazy; it's easy to cheat this checker,
    but that's deviating from the point of the ensuretypes module
    (which is just designed to keep myself honest).
    """
    def __new__(cls, st, ty, errmsg=""):
        return super().__new__(cls, st)

    def __init__(self, st, ty, errmsg=""):
        self._ty = ty
        self._errmsg = errmsg

    def __iter__(self):
        return Syntax._check_wrap(
                arg=super().__iter__(),
                ty={self._ty}, # iterator
                errmsg=self._errmsg)

    def __repr__(self):
        return f"{super().__repr__()}:{Syntax._type_name(self._ty)}"

    def __getitem__(self, index):
        if isinstance(index, slice):
            return Syntax._check_wrap(
                    arg=super().__getitem__(index),
                    ty=[self._ty, ..., str],
                    errmsg=self._errmsg)
        return Syntax._check_wrap(
                arg=super().__getitem__(index),
                ty=self._ty,
                errmsg=self._errmsg + f" Index {index} has incorrect type.")

class LazySyntaxDict(dict):
    """
    Lazy type-checker for dict-like objects
    """
    def __init__(self, dc, kty, vty, errmsg=""):
        self._kty = kty
        self._vty = vty
        self._errmsg = errmsg
        super().__init__(dc)

    def __repr__(self):
        return f"{super().__repr__()}:{Syntax._type_name(self._kty)}->{Syntax._type_name(self._vty)}"

    def __getitem__(self, key):
        return Syntax._check_wrap(
                arg=super().__getitem__(Syntax._check_wrap(
                    arg=key,
                    ty=self._kty,
                    errmsg=self._errmsg
                            + f" Key {key} has incorrect type.")),
                ty=self._vty,
                errmsg=self._errmsg
                            + f" Value at {key} has incorrect type.")
    
    def __setitem__(self, key, value):
        super().__setitem__(Syntax._check_wrap(
                arg=key,
                ty=self._kty,
                errmsg=self._errmsg
                    + f" Key {key} has incorrect type."),
                Syntax._check_wrap(
                    arg=value,
                    ty=self._vty,
                    errmsg=self._errmsg
                    + f" Assigning incorrect type to key {key}."))

class LazySyntaxIterator:
    """
    Very lazy iterator type to wrap around iterators
    """
    def __init__(self, iterator, ty, errmsg=""):
        self._it = iterator
        self._ty = ty
        self._errmsg = errmsg

    def __repr__(self):
        return f"{repr(self._it)}:{Syntax._type_name(self._ty)}"

    def __iter__(self):
        return self

    def __next__(self):
        return Syntax._check_wrap(
                arg=self._it.__next__(),
                ty=self._ty,
                errmsg=self._errmsg
                        + " Iterator yields incorrect type.")
