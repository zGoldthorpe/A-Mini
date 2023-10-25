"""
Type-checking functionality to ensure methods are used as intended.
"""

class Syntax:
    # forward declaration
    pass

class Syntax(Syntax):
    """
    Syntax object

    Checks positional and keyword argument types.

    Put types in a tuple to "union" them.
    NB: a union can tell primitive types apart, but cannot perform more
    elaborate checks such as "list of ints vs list of strings".
    To assert element types after matching with an iterable (list, dict, etc.)
    use a pair [type, cons] inside the list, where type is primitive
    (for matching) and cons is a more specific constructor.
    E.g., Syntax([int, [list, (int, 5)], [dict, {str:str}]]) expects one
    argument whose type is one of:
    - int
    - list (after which is asserted to be a list of 5 integers)
    - dict (after which is asserted to be a map from strings to strings)

    Put [type, N] to indicate type must be an iterable of N items whose
    keys specified type (use ellipses for N if arbitrary length is okay)

    Put {type0:type1} to indicate type must be a dict from type0 to type1

    Put {type} to indicate type comes from a generator of indicated type

    Put ellipses after a positional argument to act as a Kleene star (i.e.,
    match zero or more of the previous positional argument)

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
        # does not consider ellipsis type; handle externally
        if isinstance(ty, type):
            return True
        if isinstance(ty, tuple):
            for t in ty:
                if isinstance(t, type):
                    continue # primitive type
                if not isinstance(t, tuple) or len(t) != 2 or not isinstance(t[0], type):
                    raise SyntaxError("Union type must consist of primitive types or (primitive, cons) pairs")
                Syntax._verify_input(t[1])
            return True
        if isinstance(ty, list):
            if len(ty) != 2 or not isinstance(ty[1], (int, type(Ellipsis))):
                raise SyntaxError("Iterable type must be of the form (type, count)")
            return Syntax._verify_input(ty[0])
        if isinstance(ty, set):
            if len(ty) != 1:
                raise SyntaxError("Generator type must be of the form {type}")
            gty = list(ty)[0]
            return Syntax._verify_input(gty)
        if isinstance(ty, dict):
            if len(ty) != 1:
                raise SyntaxError("Dict type must be of the form {ktype : vtype}")
            kty = list(ty)[0]
            return Syntax._verify_input(kty) and Syntax._verify_input(ty[kty])
        raise SyntaxError(f"Unrecognised type {repr(ty)}")

    def __init__(self, *types, **kwtypes):
        self._types = tuple(filter(lambda t: t is not Ellipsis, types))
        # verify Syntax
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

        # other flags / etc.
        self._allow_undef_kwargs = True
        self._allow_extra_kwargs = False
        self._return_type = object

    def _type_name(ty):
        if ty is Ellipsis:
            return "..."
        if isinstance(ty, type):
            return ty.__name__
        if isinstance(ty, tuple):
            union = ", ".join(t.__name__ if isinstance(t, type)
                    else f"( {t[0].__name__} , {Syntax._type_name(t[1])} )"
                    for t in ty)
            return f"( {union}, )"
        if isinstance(ty, list):
            ty1 = "..." if ty[1] is Ellipsis else ty[1]
            return f"[ {Syntax._type_name(ty[0])}, {ty1} ]"
        if isinstance(ty, set):
            gty = list(ty)[0]
            return f"{{ {Syntax._type_name(gty)} }}"
        if isinstance(ty, dict):
            kty = list(ty)[0]
            vty = ty[kty]
            return f"{{ {Syntax._type_name(kty)} : {Syntax._type_name(vty)} }}"

    def extract_syntax(*args, **kwargs):
        return Syntax(*[type(arg) for arg in args], **{kw:type(kwargs[kw]) for kw in kwargs})

    def set_allow_undef_kwargs(self, flag):
        self._allow_undef_kwargs = flag
        return self # allow for chaining modifiers after constructor
    
    def set_allow_extra_kwargs(self, flag):
        self._allow_extra_kwargs = flag
        return self

    def __rshift__(self, ty):
        Syntax._verify_input(ty)
        self._return_type = ty
        if self._parent is not None:
            self._parent.__rshift__(ty)
        return self

    def returns(self, ty):
        return self.__rshift__(ty)

    def __or__(self, other:Syntax):
        other._parent = self
        return other

    def union(self, *args, **kwargs):
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
        if isinstance(ty, type):
            if isinstance(arg, ty):
                return arg
        if isinstance(ty, tuple):
            for t in ty:
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
                if ty[1] is Ellipsis or len(arg) == ty[1]:
                    return LazySyntaxList(arg, ty[0], errmsg=errmsg)
        if isinstance(ty, set):
            gty = list(ty)[0]
            if hasattr(arg, "__next__"):
                return LazySyntaxIterator(arg, gty, errmsg=errmsg)
                
        if isinstance(ty, dict):
            kty = list(ty)[0]
            vty = ty[kty]
            if hasattr(arg, "__iter__") and hasattr(arg, "__getitem__"):
                return LazySyntaxDict(arg, kty, vty, errmsg=errmsg)

        # at this point, arg failed typecheck
        raise TypeError(errmsg)

    def _check_one(arg, ty):
        """
        Checks if arg is of the type ty, given the conventions of the
        Syntax class
        """
        if isinstance(ty, type):
            return isinstance(arg, ty)
        if isinstance(ty, tuple):
            return any(Syntax._check_one(arg, t) for t in ty)
        if isinstance(ty, list):
            if not hasattr(arg, "__iter__"):
                return False
            if ty[1] is Ellipsis or len(arg) == ty[1]:
                return all(Syntax._check_one(a, ty[0]) for a in arg)
            return False
        if isinstance(ty, dict):
            kty = list(ty)[0]
            vty = ty[kty]
            if not hasattr(arg, "__iter__") or not hasattr(arg, "__getitem__"):
                return False
            return all(Syntax._check_one(kw, kty)
                    and Syntax._check_one(arg[kw], vty) for kw in arg)

    def check(self, func_name, *args, **kwargs):
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


    def check_return(self, func_name, retval):
        if not Syntax._check_one(retval, self._return_type):
            raise TypeError(f"{func_name} expected to return {Syntax._type_name(self._return_type)}; returned unexpected {type(retval).__name__}")
        return retval

    def __repr__(self):
        positional = ", ".join(Syntax._type_name(ty) for ty in self._types)
        keyword = ", ".join(f"{kw}:{Syntax._type_name(self._kwtypes[kw])}" for kw in self._kwtypes)
        if not positional and not keyword:
            return "Syntax() >> {Syntax._type_name(self._return_type)}"
        if not positional:
            return f"Syntax({keyword}) >> {Syntax._type_name(self._return_type)}"
        if not keyword:
            return f"Syntax({positional}) >> {Syntax._type_name(self._return_type)}"
        return f"Syntax({positional}; {keyword}) >> {Syntax._type_name(self._return_type)}"

    def caller(self, func, *args, **kwargs):
        retval = func(*args, **kwargs)
        self.check_return(func.__name__, retval)
        return retval

    def __call__(self, func):
        """
        Wrapper for type assertions
        """
        def wrap(*args, **kwargs):
            if self._parent is None:
                args, kwargs = self.check(func.__name__, *args, **kwargs)
            else:
                args, kwargs = self.check_iter(func.__name__, [], *args, **kwargs)
            retval = func(*args, **kwargs)
            return Syntax._check_wrap(
                    arg=retval,
                    ty=self._return_type,
                    errmsg=f"{func.__name__} expected to return {Syntax._type_name(self._return_type)}; returned unexpected {type(retval).__name__}")
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

    def __getitem__(self, index):
        return Syntax._check_wrap(
                arg=super().__getitem__(index),
                ty=self._ty,
                errmsg=self._errmsg + f" Index {index} has incorrect type.")

    def __setitem__(self, index, value):
        super().__setitem__(index, Syntax._check_wrap(
                arg=value,
                ty=self._ty,
                errmsg=self._errmsg + f" Assigning incorrect type to index {index}."))

def LazySyntaxDict(dict):
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
    Very lazy iterator type, for iterators
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
