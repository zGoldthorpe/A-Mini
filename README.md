# A-Mi
**A**ssembly-**Mi**nimal: a toy language for testing optimisation.

1. [About the language](#about-the-language)
1. [Running A-Mi code](#running-a-mi-code)
1. [A-Mi optimisation](#a-mi-optimisation)

## About the language

A-Mi has unlimited "virtual registers", whose names are prefixed with a `%`.
All registers store integers.

A-Mi branches are all necessarily direct, and branch labels are prefixed with a `@`.

Comments are prefixed by a semicolon `;`, and span until the end of the line.

Sample code can be found in `code/examples/`.

### Arithmetic operations

A-Mi only supports polynomial arithmetic instructions:
```
    %a = %b                             ; copy
    %a = %b + %c                        ; addition
    %a = %b - %c                        ; subtraction
    %a = %b * %c                        ; multiplication
```

The operands `%b` and `%c` may also be given by decimal integer constants.

### Comparisons

A-Mi supports integer comparison, and stores the result as either a `0` or a `1` (as an integer) to a register:
```
    %cond = %b == %c                    ; equal
    %cond = %b != %c                    ; unequal
    %cond = %b <  %c                    ; strictly less than
    %cond = %b <= %c                    ; less than or equal to
```

Again, the operands `%b` and `%c` may be given by decimal integer constants.

### Control flow

A-Mi branches are direct, and branch target labels cannot be manipulated.
```
@label:                                 ; declare a branch target
    goto @target                        ; unconditional direct branch
    branch %cond ? @iftrue : @iffalse   ; conditional branch
    exit                                ; terminate program
```
To support single static assignment (SSA), A-Mi also has a `phi` instruction.
```
%a = phi [%1, @1], [%2, @2], ...        ; variadic phi instruction
```
The value of `%a` is given by `%1` if the previous branch had source `@1`, and given by `%2` if the previous branch had source `@2`, and so on.
The operands `%1`, `%2`, and so on may also be given by decimal integer constants.

### Input and output

A-Mini allows for integers to be read (one per line) and printed (one per line).

```
    read  %a                            ; store input to register
    write %b                            ; write value of register to output
```
The register `%b` may also be given by a decimal constant.

### Debugging

A-Mini also has a built-in "breakpoint" instruction
```
    brkpt !name                         ; trigger breakpoint with given name
```
which pauses the program and allows the user to query registers.


## Running A-Mi code

The A-Mi interpreter is given by `ami.py`.
To run the interpreter, simply call
```console
python3 ami.py path/to/code.ami
```
The interpreter supports some command-line options; for instance,
```console
python3 ami.py path/to/code.ami --trace
```
outputs a trace of the execution to `stderr`.

For a list of all options for the A-Mi interpreter, just run
```console
python3 ami.py --help
```

## A-Mi code optimisation

A-Mi analyses and optimisations are managed with `amo.py`.
A generic call to the optimiser may look like
```console
python3 amo.py code.ami -o opt.ami \
    --add-pass="pass1" \
    --add-pass="pass2(arg0, arg1)" \
    --add-pass="pass3(arg0, key1=arg1)"
```
Passes are run in the order they are added to the command.
Notice that `pass2` receives two positional arguments, and `pass3` receives a positional argument and a keyword argument.

The analysed/optimised code is printed to `opt.ami`.
If an output file is not specified with `-o`, then the code is printed to `stdout`.

To see the registered passes, run
```console
python3 amo.py --list-passes
```

To see details about a particular pass, run
```console
python3 amo.py --explain "pass"
```

Of course, the list of all options for the A-Mi optimiser can be found by running
```console
python3 amo.py --help
```
