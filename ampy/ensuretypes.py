from functools import wraps

def ensure_types(*types, **kwtypes):
    """
    Wrapper to ensure inputs are of valid types
    """
    def outer(func):
        @wraps(func)
        def inner(*args, **kwargs):
            if len(args) != len(types):
                raise TypeError(f"{func.__name__} expects {len(types)} positional arguments, {len(args)} given.")
            for i, (arg, ty) in enumerate(zip(args, types)):
                if not isinstance(arg, ty):
                    raise TypeError(f"{func.__name__} expects {ty.__name__}; {type(arg).__name__} given")
            for kw in kwargs:
                if kw not in kwtypes:
                    raise TypeError(f"Unexpected keyword argument {kw} in {func.__name__}")
                if not isinstance(kwargs[kw], kwtypes[kw]):
                    raise TypeError(f"{func.__name__} keyword argument {kw} expects {kwtypes[kw].__name__}; {type(kwargs[kw]).__name__} given")
            # at this point, all checks pass
            return func(*args, **kwargs)
        return inner
    return outer

