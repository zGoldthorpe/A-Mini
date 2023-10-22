from functools import wraps

class Syntax:

    def __init__(self, *types, **kwtypes):
        self._types = types
        self._kwtypes = kwtypes
        self._allow_undef_kwargs = True
        self._allow_extra_kwargs = False

    def _type_name(ty):
        if isinstance(ty, type):
            return ty.__name__
        if isinstance(ty, tuple):
            return f"({', '.join(Syntax._type_name(t) for t in ty)})"
    def extract_syntax(*args, **kwargs):
        return Syntax(*[type(arg) for arg in args], **{kw:type(kwargs[kw]) for kw in kwargs})

    def set_allow_undef_kwargs(self, flag):
        self._allow_undef_kwargs = flag
        return self # allow for chaining modifiers after constructor
    
    def set_allow_extra_kwargs(self, flag):
        self._allow_extra_kwargs = flag
        return self

    def check(self, func_name, *args, **kwargs):
        if len(args) != len(self._types):
            raise TypeError(f"{func_name} expects {len(self._types)} positional arguments; {len(args)} given.")
        for i, (arg, ty) in enumerate(zip(args, self._types)):
            if not isinstance(arg, ty):
                raise TypeError(f"{func_name} argument {i} expects {Syntax._type_name(ty)}; {Syntax._type_name(type(arg))} given.")
        for kw in kwargs:
            if kw not in self._kwtypes:
                if self._allow_extra_kwargs:
                    continue
                raise TypeError(f"{func_name} received unexpected keyword argument {kw}.")
            if not isinstance(kwargs[kw], self._kwtypes[kw]):
                raise TypeError(f"{func_name} keyword argument {kw} expects {Syntax._type_name(self._kwtypes[kw])}; {Syntax._type_name(type(kwargs[kw]))} given.")
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
