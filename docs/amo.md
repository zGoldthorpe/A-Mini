# A-Mi code optimisation

Optimisation passes can be applied to A-Mi source code via `amo.py`.
The general syntax for optimisation is
```console
python3 amo.py code.ami \
    --add-pass="pass1" \
    --add-pass="pass2(arg0, arg1)" \
    --add-pass="pass3(arg0, key1=arg1)"
```
Any script that accepts optimisation passes have the same inline argument syntax as `amo.py`.

In the above example, the source `code.ami` is explicitly put through three passes:
- `pass1`, with no arguments passed
- `pass2`, with two positional arguments `arg0` and `arg1` passed
- `pass3`, with a positional argument `arg0`, and a key-word argument `key1` with value `arg1` passed.

Some passes may accept positional or keyword arguments to tweak their behaviour.
However, note that all passes are optional, and have default values.

To see quick information about a pass, run
```console
python3 amo.py --explain "pass"
```
To see all registered optimisation passes, run
```console
python3 amo.py --list-passes
```

For more command-line options and brief explanation, run
```console
python3 amo.py -h
```
