# The A-Mi language

1. [ISA](#the-instruction-set)
1. [Program structure](#program-structure)
1. [Runng an A-Mi program](#running-an-a-mi-program)

A-Mi is a simple assembly-like language supporting basic signed integer operations (on integers with unbounded bitlength) and simple control flow.

Most instructions have three operands (typically a target and operation arguments), and these operands can be any of the following:
- a signed integer constant
- a virtual register
- a block label

Virtual addresses (which are essentially just "integer-valued variables") are identified with a `%` prefix, whereas block labels are identified with an `@` prefix.
Integer constants may be written in decimal, or in hexadecimal (if prefixed with `0x`).

Comments are prefixed with a `;` character, and extend until the end of the line.
There are no multi-line comments.

## The instruction set

A-Mi has several classes of instructions.

1. [Copy instructions](#copy-instructions)
1. [Binary operation instructions](#binary-operations)
1. [Branch instructions](#branch-instructions)
1. [I/O instructions](#io-instructions)
1. [Breakpoints](#breakpoints)

When describing the syntax for these instructions, we will use the following shorthands:
| Shorthand | Meaning |
|:---------:|:-------:|
| `@#`      | Generic block label |
| `%#`      | Generic virtual register |
| `?#`      | Generic integer or virtual register |

### Copy instructions

The simplest copy instruction is the "move" instruction
```ami
    %0 = ?1
```
which just copies the value of `?1` into the register `%0`.

The more interesting copy instruction is the `phi` node instruction.
```ami
    %0 = phi [ ?1, @2 ], [ ?3, @4 ], ...
```
which is variadic.
This instruction copies the value of `?1` into `%0`, but only if the previous block label (prior to the current block label) is `@2`; otherwise, the instruction copies the value of `?3` into `%0` if the previous block label is `@4`; otherwise, the instruction continues to go down the list of value-label pairs until it finds a match.

A `phi` node **must** have a value corresponding to every possible previous block label, or else A-Mi will complain.

> *Note.* `phi` nodes are implemented so that A-Mi code can be written in [static single-assignment](https://en.wikipedia.org/wiki/Static_single_assignment_form) (SSA) form, but A-Mi code does not need to be in SSA form by default.

### Binary operations

All binary operations have the form
```ami
    %0 = ?1 <op> ?2
```
where `<op>` is some binary operation.
The instruction computes the given operation on the two operands `?1` and `?2`, and stores the result in register `%0`.

#### Arithmetic operations
The supported arithmetic operations are
```ami
    %0 = ?1 + ?2    ; addition
    %0 = ?1 - ?2    ; subtraction
    %0 = ?1 * ?2    ; multiplication
    %0 = ?1 / ?2    ; integer division
    %0 = ?1 % ?2    ; remainder (modulo)
```

#### Bitwise operations
The supported bitwise operations are
```ami
    %0 = ?1 & ?2    ; conjunction
    %0 = ?1 | ?2    ; disjunction
    %0 = ?1 ^ ?2    ; exclusive disjunction
    %0 = ?1 << ?2   ; bitshift left
    %0 = ?1 >> ?2   ; bitshift right
```

#### Comparison operations
The supported comparison instructions are
```ami
    %0 = ?1 == ?2   ; equality
    %0 = ?1 != ?2   ; unequality
    %0 = ?1 < ?2    ; strictly less than
    %0 = ?1 <= ?2   ; less than or equal to
```

#### Syntactic sugar
A-Mi also has *phony* (alias) instructions for convenience

| Alias           | Purpose                  | Instruction     |
|:----------------|:------------------------:|:----------------|
| `%0 = -?1`      | negation                 | `%0 = 0 - ?1`   |
| `%0 = ~?1`      | complement               | `%0 = 1 ^ ?1`   |
| `%0 = ?1 > ?2`  | strictly greater than    | `%0 = ?2 < ?1`  |
| `%0 = ?1 >= ?2` | greater than or equal to | `%0 = ?2 <= ?1` |

The parser automatically reinterprets these aliases for their underlying instructions.

### Branch instructions

Control flow is managed with three branch instructions:
```ami
    exit                ; exit point
    goto @0             ; unconditional branch
    branch %0 ? @1 : @2 ; conditional branch
```
The first two instructions are self-explanatory.
The conditional branch tests if `%0` is null.
If `%0` is nonzero, then the instruction jumps to `@1`; otherwise, it jumps to `@2`.

### I/O instructions

A-Mi has very limited I/O capabilities.
```ami
    read %0     ; read integer from line of stdin
    write ?0    ; write integer to stdin
```
The `read` instruction expects a single decimal integer as input (it also will not accept multiple space-separated integers), and stores its value into `%0`.

The `write` instruction prints the value of `?0` to a single line of the output (in decimal).

### Breakpoints

For debugging, you may insert breakpoints into A-Mi code.
```ami
    brkpt !name ; breakpoint with label "name"
```
As far as the program is concerned, this instruction does nothing.
It triggers the interpreter to enter a "debug" mode, which allows you to probe the current state of the program (i.e., query register values).

## Program structure

The entrypoint of the program is identified by the first label in the source code.
Execution starts at this point.

Labels and branch instructions naturally decompose an A-Mi program into [basic blocks](https://en.wikipedia.org/Basic_block).
- Basic blocks begin at a label, or immediately following a branch instruction.
- Basic blocks end at a branch instruction, or immediately before a label.

Basic blocks that begin immediately following a branch instruction without a label are called *anonymous* basic blocks.
Since A-Mi does not have [indirect branches](https://en.wikipedia.org/Indirect_branch), anonymous basic blocks are unreachable.
As a result, A-Mi simply **forbids anonymous blocks**.

On the other hand, source code does not need to explicitly end basic blocks with branch instructions, and instead allow the program to "fall through" to the basic block immediately following it.

```ami
    read %0         ; this starts an anonymous block, hence disallowed!
    %1 = %0 - 5
@0: read %2         ; <-- this is the entrypoint of the program (if it parsed)
    %2 = %2 + %1
    goto @1
    %2 = %2 - 1     ; this starts an anonymous block, hence disallowed1
@1: write %2        ; <-- this is a legal basic block
    read %3
    %3 = %1 + %3    ; fallthrough to @2
@2: %2 = %3 - %2    ; <-- this is a legal basic block
    write %2
```

> *Note.* Although fallthrough is permitted when *writing* A-Mi code, the parser automatically appends an unconditional branch at the end of basic blocks that fall through.
> This allows for code to be stored as an abstract [control-flow graph](https://en.wikipedia.org/wiki/Control-flow_graph), which is also convenient for the optimiser.

## Running an A-Mi program

The A-Mi interpreter is given by `ami.py`.
To run the interpreter, run
```console
python3 ami.py path/to/code.ami
```
The interpreter has several command-line options to control its behaviour.
For instance, the `--trace` option has the interpreter output the program execution trace to `stderr`.

The interpreter also supports passing the input code through optimisations:
```console
python3 ami.py path/to/code.ami --add-pass="pass"
```
(see [A-Mi code optimisation](amo.md) for more.)

To see the full list of command-line options, run
```console
python3 ami.py -h
```
