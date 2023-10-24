from functools import wraps

class Syntax:
    """
    Syntax object

    Checks positional and keyword argument types.

    Put types in a tuple to "union" them.

    Put [type, N] to indicate type must be an iterable of N items whose
    keys specified type (use ellipses for N if arbitrary length is okay)

    Put {type0:type1} to indicate type must be a dict from type0 to type1

    Put ellipses after an optional positional argument to make
    previous argument optional (i.e., ellipses act as a Kleene star).
    """
    
    def _verify_input(ty):
        # does not consider ellipsis type; handle externally
        if isinstance(ty, type):
            return True
        if isinstance(ty, tuple):
            return all(Syntax._verify_input(t) for t in ty)
        if isinstance(ty, list):
            if len(ty) != 2 or not isinstance(ty[1], (int, type(Ellipsis))):
                raise SyntaxError("Iterable type must be of the form [type, count]")
            return Syntax._verify_input(ty[0])
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

        self._allow_undef_kwargs = True
        self._allow_extra_kwargs = False

    def _type_name(ty):
        if ty is Ellipsis:
            return "..."
        if isinstance(ty, type):
            return ty.__name__
        if isinstance(ty, tuple):
            return f"({', '.join(Syntax._type_name(t) for t in ty)})"
        if isinstance(ty, list):
            return f"[ {Syntax._type_name(ty[0])}, {ty[1]} ]"
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

    def _check_one(arg, ty):
        if isinstance(ty, type):
            return isinstance(arg, ty)
        if isinstance(ty, tuple):
            return any(Syntax._check_one(arg, t) for t in ty)
        if isinstance(ty, list):
            if not hasattr(arg, "__iter__"):
                return False
            return all(Syntax._check_one(a, ty[0]) for a in arg)
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
        for i, (arg, ty) in enumerate(zip(args, types)):
            if not Syntax._check_one(arg, ty):
                raise TypeError(f"{func_name} argument {i} expects {Syntax._type_name(ty)}; unexpected {Syntax._type_name(type(arg))} given.")
        for kw in kwargs:
            if kw not in self._kwtypes:
                if self._allow_extra_kwargs:
                    continue
                raise TypeError(f"{func_name} received unexpected keyword argument {kw}.")
            if not Syntax._check_one(kwargs[kw], self._kwtypes[kw]):
                raise TypeError(f"{func_name} keyword argument {kw} expects {Syntax._type_name(self._kwtypes[kw])}; unexpected {Syntax._type_name(type(kwargs[kw]))} given.")
        if not self._allow_undef_kwargs:
            for kw in self._kwtypes:
                if kw not in kwargs:
                    raise TypeError(f"{func_name} missing expected keyword {kw}.")

    def __repr__(self):
        positional = ", ".join(ty.__name__ for ty in self._types)
        keyword = ", ".join(f"{kw}:{Syntax._type_name(self._kwtypes[kw])}" for kw in self._kwtypes)
        if not positional and not keyword:
            return "Syntax()"
        if not positional:
            return f"Syntax({keyword})"
        if not keyword:
            return f"Syntax({positional})"
        return f"Syntax({positional}; {keyword})"

def ensure_types(*types, **kwtypes):
    """
    Wrapper to ensure inputs are of valid types
    """
    def outer(func):
        @wraps(func)
        def inner(*args, **kwargs):
            Syntax(*types, **kwtypes).check(func.__name__, *args, **kwargs)
            return func(*args, **kwargs)
        return inner
    return outer

def ensure_multi(*syntaxes):
    """
    Wrapper to ensure inputs to a function with multiple instantiations
    commits to a single set of types
    Syntaxes may be given by a single Syntax object, or as a (clue, total) pair.
    If the "clue" makes a partial match, then "total" must match completely.
    """
    syntaxes = list(syntaxes)
    for i, syntax_p in enumerate(syntaxes):
        if isinstance(syntax_p, Syntax):
            syntaxes[i] = (syntax_p, syntax_p)
            continue
        assert(isinstance(syntax_p, tuple) and len(syntax_p) == 2)
        clue, total = syntax_p
        assert(isinstance(clue, Syntax) and isinstance(total, Syntax))

    def outer(func):
        @wraps(func)
        def inner(*args, **kwargs):
            for clue, syntax in syntaxes:
                commit = True
                clue.set_allow_extra_kwargs(True)
                try:
                    clue.check(func.__name__, *args, **kwargs)
                except TypeError:
                    commit = False
                if commit:
                    syntax.check(func.__name__, *args, **kwargs)
                    return func(*args, **kwargs)
            # if this line is reached, then none of the clues matched
            raise TypeError(f"""{Syntax._type_name(func)} received unrecognised argument pattern
\t{repr(Syntax.extract_syntax(*args, **kwargs))}
Valid syntaxes are:
\t{(chr(10)+chr(9)).join(repr(syntax) for _, syntax in syntaxes)}""")
        return inner
    return outer
