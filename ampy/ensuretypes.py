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
import re
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

    ((), type0, type1 [, ...])
        Match to a tuple where each argument has a distinct specified type.
        These types may be elaborate.

    [container, type, [lo, hi]]
        Type must be a container-like iterable of entries of specified
        type, where the number of entries is bounded between lo and hi,
        inclusive.
        Use ellipses for lo or hi to indicate unboundedness in either
        direction.

        [*, type, N] is shorthand for [*, type, [N, N]]
        [*, type] is shorthand for [*, type, ...] = [*, type, [...,...]]
        [type, *] is shorthand for [list, type, *]

    [iter, type]
        Type must be an iterator that generates a specified type.

    {type0 : type1}
        Type must be a dict from type0 to type1

    slice(start, stop, step)
        Type is a slice object whose start, stop, and step types are as specified

    lambda : Syntax(*args, **kwargs) >> type
        Type must be a function with specified syntax

    "regex"
        Type must be a string which fully matches RegEx pattern provided

    Assertion(func)
        Type must evaluate to True under "func"

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
    
    .set_allow_extra_kwargs(flag, ty=object):
        toggle if function calls with unanticipated kwargs are permissible, and assert
        they have a specified type ty
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

        Returns the verified type (in case it needs to be modified)
        or throws a SyntaxError

        Does not handle ellipses; handle these externally
        """
        if ty is None:
            # NoneType
            return ty

        if isinstance(ty, type):
            # primitive type
            return ty

        if isinstance(ty, tuple):
            # union or tuple
            if len(ty) > 0 and ty[0] == ():
                # this is a tuple match
                return ((),) + tuple(Syntax._verify_input(t) for t in ty[1:])
            
            # otherwise, it is a union
            newty = []
            for t in ty:
                if t is None:
                    newty.append(t)
                    continue
                if isinstance(t, type):
                    newty.append(t)
                    continue # primitive type
                if not isinstance(t, tuple) or len(t) != 2 or not isinstance(t[0], type):
                    raise SyntaxError("Union type must consist of primitive types or (primitive, cons) pairs")
                # (hint, type) pair
                newty.append((t[0], Syntax._verify_input(t[1])))
            return tuple(newty)

        if isinstance(ty, str):
            try:
                re.compile(ty)
                return ty
            except SyntaxError as e:
                raise SyntaxError(f"\"{ty}\" is not a valid regular expression\n{e}")

        if isinstance(ty, slice):
            return slice(Syntax._verify_input(ty.start),
                         Syntax._verify_input(ty.stop),
                         Syntax._verify_input(ty.step))

        if isinstance(ty, list):
            # iterable of fixed element type
            errmsg = "Iterable type must be of the form [container, type, count]"
            containers = (list, set, tuple, str)

            # unpack shorthands
            match len(ty):
                case 1: # [type] = [list, type, ...]
                    ty.insert(0, list)
                    ty.append(Ellipsis)
                case 2: # [container, type] or [type, count] or [iter, type]
                    if ty[0] == iter:
                        # [iter, type]
                        return [iter, Syntax._verify_input(ty[1])]
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
                print(ty)
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
            return [ty[0], Syntax._verify_input(ty[1]), ty[2]]

        if isinstance(ty, dict):
            # dictionary of fixed key-value type pairing
            if len(ty) != 1:
                raise SyntaxError("Dict type must be of the form {ktype : vtype}")
            kty = list(ty)[0]
            return {Syntax._verify_input(kty) : Syntax._verify_input(ty[kty])}

        if isinstance(ty, FunctionType):
            # function must have zero arity
            errmsg = "Function type must be of the form lambda:Syntax(*args, **kwargs)."
            try:
                syntax = ty()
            except TypeError:
                raise SyntaxError(errmsg + " Lambda has nonzero arity.")
            if not isinstance(syntax, Syntax):
                raise SyntaxError(errmsg + " Lambda does not return Syntax object")
            return ty

        if isinstance(ty, Assertion):
            if ty.message is None:
                ty.message = "{arg} fails assertion"
            return ty

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
            pretypes.append(Syntax._verify_input(ty))
        self._types = tuple(pretypes)
        
        self._kwtypes = dict()
        for kw in kwtypes:
            self._kwtypes[kw] = Syntax._verify_input(kwtypes[kw])

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
            if len(ty) > 0 and ty[0] == ():
                tp = ", ".join(Syntax._type_name(t) for t in ty[1:])
                return f"((), {tp})"

            union = ", ".join("None" if t is None
                    else t.__name__ if isinstance(t, type)
                    else f"( {t[0].__name__} , {Syntax._type_name(t[1])} )"
                    for t in ty)
            return f"( {union}, )"

        if isinstance(ty, str):
            return f"r\"{ty}\""

        if isinstance(ty, slice):
            start = Syntax._type_name(ty.start)
            stop = Syntax._type_name(ty.stop)
            step = Syntax._type_name(ty.step)
            return f"slice({start}, {stop}, {step})"

        if isinstance(ty, list):
            if ty[0] == iter:
                return f"[ iter, {Syntax._type_name(ty[1])} ]"
            ty0 = ty[0].__name__
            ty1 = Syntax._type_name(ty[1])
            lo, hi = map(lambda t: "..." if t is Ellipsis else t, ty[2])
            return f"[ {ty0}, {ty1}, [ {lo}, {hi} ] ]"

        if isinstance(ty, dict):
            kty = list(ty)[0]
            vty = ty[kty]
            return f"{{ {Syntax._type_name(kty)} : {Syntax._type_name(vty)} }}"

        if isinstance(ty, FunctionType):
            syntax = ty()
            return f"lambda : {repr(syntax)}"

        if isinstance(ty, Assertion):
            return f"<assertion>"

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
    
    def set_allow_extra_kwargs(self, flag, ty=object):
        """
        Toggle whether Syntax permits (if True) arguments passed
        to the function that do not have a type assertion provided
        to the Syntax instance
        """
        self._allow_extra_kwargs = flag
        self._extra_kwarg_ty = Syntax._verify_input(ty)
        return self

    def __rshift__(self, ty):
        """
        Set return type of Syntax
        """
        self._return_type = Syntax._verify_input(ty)
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

    def _check(arg, ty, errmsg=""):
        """
        Lazily check if arg is of type ty, given conventions of the
        Syntax class
        """
        if ty is None:
            if arg is None:
                return arg
            raise TypeError(errmsg + f"\nExpected NoneType, but received {type(arg).__name__}.")

        if isinstance(ty, type):
            if isinstance(arg, ty):
                return arg
            raise TypeError(errmsg + f"\nExpected {ty.__name__}, but received {type(arg).__name__}.")

        if isinstance(ty, tuple):
            if len(ty) > 0 and ty[0] == ():
                # tuple match
                if len(arg) != len(ty)-1:
                    raise TypeError(errmsg + f"\nTuple has incorrect length: expected {len(ty)-1}, but got {len(arg)}.")
                return tuple(Syntax._check(a, t, errmsg=errmsg+f"\nElement {i} in tuple of incorrect type.")
                                for i, (a, t) in enumerate(zip(arg, ty[1:])))
            # or union
            for t in ty:
                if t is None:
                    if arg is None:
                        return arg
                elif isinstance(t, type):
                    if isinstance(arg, t):
                        return arg
                else:
                    mty, cons = t
                    if isinstance(arg, mty):
                        # primitive match, so assert elaborate type "cons"
                        return Syntax._check(arg, cons, errmsg=errmsg)
            raise TypeError(errmsg + f"\nFailed to match any of {Syntax._type_name(ty)}")

        if isinstance(ty, str):
            if isinstance(arg, str):
                if re.fullmatch(ty, arg) is not None:
                    return arg
                raise TypeError(errmsg + f"\n\"{arg}\" does not match regular expression {Syntax._type_name(ty)}")
            raise TypeError(f"Regular expression expects a string; received {type(arg).__name__}")

        if isinstance(ty, slice):
            if isinstance(arg, slice):
                return slice(Syntax._check(arg.start, ty.start, errmsg=errmsg),
                        Syntax._check(arg.stop, ty.stop, errmsg=errmsg),
                        Syntax._check(arg.step, ty.step, errmsg=errmsg))
            raise TypeError(errmsg + f"\n{Syntax._type_name(ty)} expects a slice; received {type(arg).__name__}")

        if isinstance(ty, list):
            if ty[0] == iter:
                # generator, so treat separately
                if hasattr(arg, "__next__"):
                    if isinstance(arg, TypedIterator):
                        arg._ty = ty[1]
                        return arg
                    return TypedIterator(arg, ty[1], errmsg=errmsg)
                raise TypeError(errmsg + f"\n{Syntax._type_name(ty)} expects iterator; received {type(arg).__name__}")

            # otherwise, it is an iterable
            if hasattr(arg, "__len__"):
                lo, hi = ty[2]
                lo = 0 if lo is Ellipsis else lo
                hi = len(arg) if hi is Ellipsis else hi
                if lo <= len(arg) <= hi:
                    if ty[0] == list:
                        if isinstance(arg, TypedList):
                            arg._ty = ty[1]
                            return arg
                        return TypedList(arg, ty[1], errmsg=errmsg)
                    if ty[0] == set:
                        if isinstance(arg, TypedSet):
                            arg._ty = ty[1]
                            return arg
                        return TypedSet(arg, ty[1], errmsg=errmsg)
                    if ty[0] == tuple:
                        if isinstance(arg, TypedTuple):
                            arg._ty = ty[1]
                            return arg
                        return TypedTuple(arg, ty[1], errmsg=errmsg)
                    if ty[0] == str:
                        if isinstance(arg, TypedString):
                            arg._ty = ty[1]
                            return arg
                        return TypedString(arg, ty[1], errmsg=errmsg)
                raise TypeError(errmsg + f"\nIterable {arg} does not have appropriate length to match {Syntax._type_name(ty)}")
            raise TypeError(errmsg + f"\n{Syntax._type_name(ty)} expects an iterable; received {type(arg).__name__}")
                
        if isinstance(ty, dict):
            kty = list(ty)[0]
            vty = ty[kty]
            if hasattr(arg, "__iter__") and hasattr(arg, "__getitem__"):
                if isinstance(arg, TypedDict):
                    arg._kty = kty
                    arg._vty = vty
                    return arg
                return TypedDict(arg, kty, vty, errmsg=errmsg)
            raise TypeError(errmsg + f"\n{Syntax._type_name(ty)} expects dictionary; received {type(arg).__name__}")

        if isinstance(ty, FunctionType):
            syntax = ty()
            if isinstance(arg, FunctionType):
                return syntax(arg)
            raise TypeError(errmsg + f"\n{Syntax._type_name(ty)} expects function; received {type(arg).__name__}")

        if isinstance(ty, Assertion):
            if ty(arg):
                return arg
            # assertion throws a TypeError on failure

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
                Syntax._check(
                    arg=P[1][0], # arg
                    ty=P[1][1], # type
                    errmsg=f"{func_name} argument {P[0]} expects {Syntax._type_name(P[1][1])}; unexpected {type(P[1][0]).__name__} given."),
                enumerate(zip(args, types)))
        wrapped_kwargs = dict()
        for kw in kwargs:
            if kw not in self._kwtypes:
                if self._allow_extra_kwargs:
                    wrapped_kwargs[kw] = Syntax._check(
                            arg=kwargs[kw],
                            ty=self._extra_kwarg_ty,
                            errmsg=f"Extra keyword arguments to {func_name} (such as {kw}) must have type {Syntax._type_name(self._extra_kwarg_ty)}; unexpected {Syntax._type_name(type(kwargs[kw]))}")
                    continue
                raise TypeError(f"{func_name} received unexpected keyword argument {kw}.")
            wrapped_kwargs[kw] = Syntax._check(
                        arg=kwargs[kw],
                        ty=self._kwtypes[kw],
                        errmsg=f"{func_name} keyword argument {kw} expects {Syntax._type_name(self._kwtypes[kw])}; unexpected {Syntax._type_name(type(kwargs[kw]))} given.")
        if not self._allow_undef_kwargs:
            for kw in self._kwtypes:
                if kw not in kwargs:
                    raise TypeError(f"{func_name} missing expected keyword {kw}.")

        return wrapped_args, wrapped_kwargs

    def check_recursive(self, func_name, viz, *args, **kwargs):
        """
        If Syntax is part of a union, recursively check all instances
        in the union and find the first match (in reverse order of
        instantiation).

        Returns args and kwargs modified according to the first ancestor
        to (lazily) accept the arguments.
        """
        try:
            # use new names in case the exception happens after self.check
            new_args, new_kwargs = self.check(func_name, *args, **kwargs)
            new_args = tuple(new_args) # force type check
            return new_args, new_kwargs
        except Exception as e:
            if self._parent is None:
                raise TypeError(f"""{func_name} received unrecognised argument pattern
\t{repr(Syntax.extract_syntax(*args, **kwargs))}
Valid syntaxes are:
\t{viz.replace(chr(10), chr(10)+chr(9))}""")
            return self._parent.check_recursive(func_name, viz, *args, **kwargs)

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
        def Syntax_call_wrap(*args, **kwargs):
            if self._parent is None:
                args, kwargs = self.check(func.__name__, *args, **kwargs)
            else:
                args, kwargs = self.check_recursive(func.__name__, repr(self), *args, **kwargs)
            retval = func(*args, **kwargs)
            return Syntax._check(
                    arg=retval,
                    ty=self._return_type,
                    errmsg=f"{func.__name__} expected to return {Syntax._type_name(self._return_type)}; returned unexpected {type(retval).__name__}.")

        Syntax_call_wrap.__doc__ = repr(self) + (f"\n{func.__doc__}" if func.__doc__ is not None else "")

        return Syntax_call_wrap

class Assertion:

    def __init__(self, assertion, message=None):
        """
        Assertion type
        Takes a unary function and, when passed an argument, asserts that
        this function returns True
        Otherwise, throws an error.
        The message can contain {arg}, which would be replaced by the argument passed
        """
        if not isinstance(assertion, FunctionType):
            raise SyntaxError("Assertion requires assertion to be a function")
        self._assertion = assertion
        self.message = message

    def __call__(self, arg):
        try:
            res = self._assertion(arg)
        except TypeError:
            raise SyntaxError("Assertion function must have arity 1")

        if not res:
            raise TypeError(self.message.format(arg=arg))

        return True

    def __repr__(self):
        return "Assertion"

class TypedList(list):
    """
    Lazy type-checker for list-like iterable

    Implementation is also lazy; it's easy to cheat this checker,
    but that's deviating from the point of the ensuretypes module
    (which is just designed to keep myself honest).
    """
    def __init__(self, ls, ty, errmsg=""):
        self._ty = Syntax._verify_input(ty)
        self._errmsg = errmsg
        super().__init__(ls)

    def __repr__(self):
        return f"{super().__repr__()}:{Syntax._type_name(self._ty)}"
    
    def __iter__(self):
        return TypedIterator(super().__iter__(), self._ty, errmsg=self._errmsg)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return Syntax._check(
                    arg=super().__getitem__(index),
                    ty=[list, self._ty, [..., ...]],
                    errmsg=self._errmsg)
        return Syntax._check(
                arg=super().__getitem__(index),
                ty=self._ty,
                errmsg=self._errmsg + f" Index {index} has incorrect type.")

    def __setitem__(self, index, value):
        super().__setitem__(index, Syntax._check(
                arg=value,
                ty=self._ty,
                errmsg=self._errmsg + f" Assigning incorrect type to index {index}."))

class TypedSet(set):
    """
    Lazy type-checker for set-like iterable
    """
    def __new__(cls, st, ty, errmsg=""):
        return super().__new__(cls)

    def __init__(self, st, ty, errmsg=""):
        self._ty = Syntax._verify_input(ty)
        self._errmsg = errmsg
        super().__init__(st)

    def __repr__(self):
        return f"{repr(set(self))}:{Syntax._type_name(self._ty)}"
    
    def __iter__(self):
        return TypedIterator(super().__iter__(), self._ty, errmsg=self._errmsg)

    def pop(self):
        return Syntax._check(
                arg=super().pop(),
                ty=self._ty,
                errmsg=self._errmsg + " Set popped incorrect type.")

    def add(self, item):
        super().add(Syntax._check(
                arg=item,
                ty=self._ty,
                errmsg=self._errmsg + " Trying to add incorrect type."))

    @property
    def type(self):
        return self._ty

class TypedTuple(tuple):
    """
    Lazy type-checker for tuple-like iterable
    """
    def __new__(cls, tp, ty, errmsg=""):
        # tuple is immutable
        return super().__new__(cls, tp)

    def __init__(self, tp, ty, errmsg=""):
        self._ty = Syntax._verify_input(ty)
        self._errmsg = errmsg
    
    def __iter__(self):
        return TypedIterator(super().__iter__(), self._ty, errmsg=self._errmsg)

    def __repr__(self):
        return f"{super().__repr__()}:{Syntax._type_name(self._ty)}"

    def __getitem__(self, index):
        if isinstance(index, slice):
            return Syntax._check(
                    arg=super().__getitem__(index),
                    ty=[self._ty, ..., tuple],
                    errmsg=self._errmsg)
        return Syntax._check(
                arg=super().__getitem__(index),
                ty=self._ty,
                errmsg=self._errmsg + f" Index {index} has incorrect type.")

class TypedString(str):
    """
    Lazy type-checker for string-like iterable

    Implementation is also lazy; it's easy to cheat this checker,
    but that's deviating from the point of the ensuretypes module
    (which is just designed to keep myself honest).
    """
    def __new__(cls, st, ty, errmsg=""):
        return super().__new__(cls, st)

    def __init__(self, st, ty, errmsg=""):
        self._ty = Syntax._verify_input(ty)
        self._errmsg = errmsg

    def __iter__(self):
        return TypedIterator(super().__iter__(), self._ty, errmsg=self._errmsg)

    def __repr__(self):
        return f"{super().__repr__()}:{Syntax._type_name(self._ty)}"

    def __getitem__(self, index):
        if isinstance(index, slice):
            return Syntax._check(
                    arg=super().__getitem__(index),
                    ty=[self._ty, ..., str],
                    errmsg=self._errmsg)
        return Syntax._check(
                arg=super().__getitem__(index),
                ty=self._ty,
                errmsg=self._errmsg + f" Index {index} has incorrect type.")

class TypedDict(dict):
    """
    Lazy type-checker for dict-like objects
    """
    def __init__(self, dc, kty, vty, errmsg=""):
        self._kty = Syntax._verify_input(kty)
        self._vty = Syntax._verify_input(vty)
        self._errmsg = errmsg
        super().__init__(dc)

    def __repr__(self):
        return f"{super().__repr__()}:{Syntax._type_name(self._kty)}->{Syntax._type_name(self._vty)}"

    def __getitem__(self, key):
        return Syntax._check(
                arg=super().__getitem__(Syntax._check(
                    arg=key,
                    ty=self._kty,
                    errmsg=self._errmsg
                            + f" Key {key} has incorrect type.")),
                ty=self._vty,
                errmsg=self._errmsg
                            + f" Value at {key} has incorrect type.")
    
    def __setitem__(self, key, value):
        super().__setitem__(Syntax._check(
                arg=key,
                ty=self._kty,
                errmsg=self._errmsg
                    + f" Key {key} has incorrect type."),
                Syntax._check(
                    arg=value,
                    ty=self._vty,
                    errmsg=self._errmsg
                    + f" Assigning incorrect type to key {key}."))

    def __iter__(self):
        return TypedIterator(super().__iter__(), self._kty, errmsg=self._errmsg)

    def __hash__(self):
        return hash(tuple(self.items()))

    def get(self, key, default=None):
        return Syntax._check(
                arg=super().get(Syntax._check(
                        arg=key,
                        ty=self._kty,
                        errmsg=self._errmsg
                            + f" Key {key} has incorrect type."),
                    default),
                ty=self._vty,
                errmsg=self._errmsg
                    + f" Get yields incorrect type for key {key}.")

    def pop(self, key, default=None):
        return Syntax._check(
                arg=super().pop(Syntax._check(
                        arg=key,
                        ty=self._kty,
                        errmsg=self._errmsg
                            + f" Key {key} has incorrect type."),
                    default),
                ty=self._vty,
                errmsg=self._errmsg
                    + f" Pop yields incorrect type for key {key}.")

    def popitem(self):
        k, v = super().popitem()
        return (Syntax._check(
                    arg=k,
                    ty=self._kty,
                    errmsg=self._errmsg
                            + f" Key {k} has incorrect type."),
                Syntax._check(
                    arg=v,
                    ty=self._vty,
                    errmsg=self._errmsg
                            + f" Value {v} has incorrect type."))

    def setdefault(self, key, default=None):
        return Syntax._check(
                arg=super().setdefault(Syntax._check(
                        arg=key,
                        ty=self._kty,
                        errmsg=self._errmsg
                                + f" Key {key} has incorrect type."),
                    Syntax._check( # explicit check since it assigns default if key is not found
                        arg=default,
                        ty=self._vty,
                        errmsg=self._errmsg
                                + f" Default {default} has incorrect type.")),
                ty=self._vty,
                errmsg=self._errmsg
                        + f" Setdefault yields incorrect type for key {key}.")

class TypedIterator:
    """
    Very lazy iterator type to wrap around iterators
    """
    def __init__(self, iterator, ty, errmsg=""):
        self._it = iterator
        self._ty = Syntax._verify_input(ty)
        self._errmsg = errmsg

    def __repr__(self):
        return f"{repr(self._it)}:{Syntax._type_name(self._ty)}"

    def __iter__(self):
        return self

    def __next__(self):
        return Syntax._check(
                arg=self._it.__next__(),
                ty=self._ty,
                errmsg=self._errmsg
                        + " Iterator yields incorrect type.")
