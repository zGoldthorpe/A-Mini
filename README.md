# A-Mini
Assembly-Minimal: a toy language for testing optimisation

## Language specs

A/Mini uses virtual registers of the form `%[.\w]+`, which are all of `int` type.
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

Every time a breakpoint is reached, the program stalls and spits out its current state.
