# A-Mi
**A**ssembly-**Mi**nimal: a toy language for testing optimisation

## Language specs

A-Mi uses "virtual registers" of the form `%[.\w]+`, which are all of `int` type.
Decimal constants are also supported, but obviously cannot be assigned to.

Program locations (for branches) require explicit labels of the form `@[.\w]+`.
Every label must be unique.
Branch targets are necessarily labelled.

Comments are prefixed with a semicolon (`;`).
The language is capable of the following operations:

```
; move
%res  = %a
%res  = phi [%a1, @lbl1], [%a2, @lbl2], ...
; arithmetic
%sum  = %a + %b
%diff = %a - %b
%prod = %a * %b
; comparisons
%eq   = %a == %b
%neq  = %a != %b
%lt   = %a < %b
%leq  = %a <= %b
; branching
@label:
goto   @label
branch %cond ? @iftrue : @iffalse
; I/O
read    %in
write   %out
; debugging
brkpt   !name
; exiting
exit
```

There is a `phi` instruction, but code does not need to be in SSA form.

`read` only accepts decimal integers, and `write` prints an integer in decimal in a single line to output.

Every time a breakpoint is reached, the program stalls, and you can interface with its current state.

### Metadata

Metadata is provided to instructions, blocks, or the entire program via comments with a specified prefix:

- `;#!arg: ...` pass `arg` to entire program (with value `...`)
- `;@!arg: ...` pass `arg` to current basic block (with value `...`)
- `;%!arg: ...` pass `arg` to current instruction (with value `...`)

The value `...` is treated as a space-separated list of strings

Instruction metadata can be passed from subsequent lines, so long as they are not preceded by
- another instruction
- a new label (and thus the start of a new basic block)
In the former case, the metadata will be assigned to the most recent instruction.
In the latter case, the metadata will not be assigned anywhere
