# Visualising A-Mi control flow

The command
```console
python3 ami2dot.py path/to/code.ami
```
spits out [DOT code](https://graphviz.org/doc/info/lang.html) describing the control flow graph (CFG) for the provided source code.
This output may then be piped through your favourite renderer (such as `dot`) to convert it into an image or a PDF; for instance:
```console
python3 ami2dot.py code.ami | dot -Tpdf > code.pdf
```
will produce a PDF visualising the CFG for `code.ami`.

The script `ami2dot.py` can also run the input code through [optimisation passes](amo.md) prior to producing DOT output.
Run
```console
python3 ami2dot.py -h
```
for an explanation of all of the script's options.
Below is a summary of the DOT-related ones.

## Improving CFG readability

By default, the produced DOT file is faithful to the provided code and optimisations (except for comments and metadata): each node corresponds to a basic block, and contains all of the block's instructions.
There are a few options that you can pass that simplify the output (and move away from A-Mi-specific syntax).

| Flag | Effect |
|:-----|:-------|
| [`--hide-phi-labels`](#hide-phi-labels) | remove labels associated to each argument of a `phi` node. |
| [`--math`](#pseudocode) | rewrite code as pseudocode |
| [`--simple-branch`](#hide-branch-instructions) | remove branch target labels |

The `--nice` flag is shorthand for enabling some of the above, depending on if the output is a plain DOT file, or [TeX source](#latex-friendly-output).

### Hide phi labels

The flag `--hide-phi-labels` converts a `phi` instruction such as
```
%x = phi [ %a, @A ], [ %b, @B ], [ 9, @C ]
```
into the more terse
```
%x = phi(%a, %b, 9)
```
> *Note.* The information lost through this simplification may not be recoverable: the order of arguments to the `phi` node will likely be unrelated to the relative positions of incoming arrows in the rendered DOT graph!

### Pseudocode

This flag `--math` tries to represent A-Mi code in a way that avoids the syntax decisions of the language.
For example, the basic block
```
@A:
    %x = %a < %b
    branch %x ? @B : @C
```
effectively changes into
```
@A:
    x = a < b
    if (x) goto @B
    goto @C
```

### Hide branch instructions

The control flow of the code can be inferred from the CFG alone, so branch instructions carry some redundant information.
The flag `--simple-branch` eliminates these redundancies:
- unconditional branches (`goto`s) are removed
- conditional branches are reduced to `if` statements
- `exit` nodes are untouched (even though they could have been removed too)

In the situation of a conditional branch, note that the outgoing edge is solid only if it corresponds to the path taken if the branch condition holds (and is otherwise dashed), so no information is lost.

## LaTeX-friendly output

To produce a DOT file that is LaTeX-friendly (in the sense that it is compatible with [`dot2tex`](https://dot2tex.readthedocs.io/en/latest/)), run
```console
python3 ami2dot.py --latex path/to/code.ami
```

By default, the output tries to be faithful to the original code.
Combine `--latex` with the [other flags](#improving-cfg-readability) to improve the readability.

For example (and reference), a nice pipeline for producing (relatively) readable pseudocode from A-Mi source is
```console
python3 ami2dot.py code.ami --latex --nice \
    | dot2tex --autosize -traw -ftikz --code > code.tex
```
after which `code.tex` may be `\input` directly into a `tikzpicture` environment.
