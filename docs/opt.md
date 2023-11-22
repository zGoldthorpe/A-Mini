# Writing an optimisation pass

This document outlines the general rules for writing an optimisation pass for A-Mi.
We will more or less rebuild the following (heavily-documented) passes:
```
opt/example/example_analysis.py
opt/example/example_opt.py
```

**Table of contents**
1. [Boilerplate](#boilerplate)
1. [The initialiser](#the-initialiser)
1. [The optimiser](#the-optimiser)
1. [Managing metadata](#managing-metadata)
1. [Debugging](#debugging)
1. [Bootstrapping off other passes](#bootstrapping-off-other-passes)
1. [Registering the pass](#registering-the-pass)
1. [Testing](#testing)

## Boilerplate

For the sake of being uniformly managed, every optimisation pass has to have the same entrypoints:

```python
from opt.tools import Opt

class Template(Opt):
    # forward declaration
    pass

class Template(Template):
    """
    TODO: docstring
    """
    @Template.init("template", ...)
    def __init__(self, ...):
        pass

    @Template.opt_pass
    def template_pass(self):
        raise NotImplementedError
```
The forward declaration is a hack to ensure that the appropriate wrappers are available for the `init` and `opt_pass` methods of the optimisation.

## The initialiser

The initialiser method is where the optimisation arguments are declared and handled (as well as what is usually done in a constructor for a class).
Consider the constructor for the `example_analysis` pass:

```python
class ExampleAnalysis(ExampleAnalysis):
    # ...
    @ExampleAnalysis.init("example_analysis", "add", count="blocks")
    def __init__(self, instr_tracker, *, count):
        # ...
```

The first argument passed to `ExampleAnalysis.init` specifies the pass ID, which is how [`amo.py`](amo.md) (or other optimisation scripts) will refer to the pass after it is registered.

The next arguments describe the **default values for all arguments** of the pass.
In particular, all arguments to a pass must be optional and have default parameters.

Then, the actual `__init__` function should accept (besides `self`) an argument for each of the default values specified above.

> *Note.* All arguments must be of string type (since they are passed via the command-line).
>
> Validity of arguments must be checked explicitly by you.
> If an invalid argument is passed, throw an `ampy.passmanager.BadArgumentException`.

### Writing pass documentation

The documentation for the pass (which, for instance, may be accessed via `amo.py --explain <pass>`) is given by the *class* docstring.

In the docstring, summarise the purpose of the optimisation pass, and explain the parameters (if applicable).

When describing pass parameters, be sure to use consistent names with the names of the variables passed to the pass `__init__` method.
The pass ID, the names of its parameters, as well as the default values, are generated automatically.
For instance, the docstring for the `ExampleAnalysis` is
```python
class ExampleAnalysis(ExampleAnalysis):
    """
    Example analysis pass to demonstrate some opt functionality.
    Locally indexes every instruction in each block.

    instr_tracker: "add" or "mul"
        for each block, track indices of adds or mults, resp.

    count="blocks" or "instructions":
        counts the total number of blocks or instructions in CFG
    """
    @ExampleAnalysis.init("example_analysis", "add", count="blocks")
    def __init__(self, instr_tracker, *, count):
        # ...
```
and (if the pass is [registered](#registering-the-pass)) the corresponding output for `amo.py --explain example_analysis` is
```
example_analysis = example_analysis(add, count=add) (opt.example.example_analysis.ExampleAnalysis)

example_analysis(instr_tracker, *, count)

    Example analysis pass to demonstrate some opt functionality.
    Locally indexes every instruction in each block.

    instr_tracker: "add" or "mul"
        for each block, track indices of adds or mults, resp.

    count="blocks" or "instructions":
        counts the total number of blocks or instructions in CFG
```

> *Tip.* If the automatically-generated header for your pass is not rendering properly (e.g., the keyword arguments are not displaying), the cause is likely because you did not clearly separate your positional and keyword arguments in the pass `__init__` method.
>
> Use a `*` to separate the positional and keyword arguments, or use `/` at the end to indicate that there are *no* keyword arguments.

## The optimisation

The other required entrypoint of the optimiser pass is the actual optimisation function.
For example, the `example_analysis` pass has the method
```python
class ExampleAnalysis(ExampleAnalysis):
    # ...
    @ExampleAnalysis.opt_pass
    def get_info(self):
        # ...
        return self.opts
```

The optimisation pass can have any name (well, except perhaps names that conflict with existing method wrappers), and are identified with the `opt_pass` wrapper.

The optimisation pass must be a function that only takes `self` as input, and the return value of an optimisation pass must be a list or tuple of optimisation classes indicating which passes were "preserved" after the completion of this pass.

### Preserved passes

Some passes may provide information about a program that may be useful for other optimisation passes.
It is therefore important that such information can be trusted to be valid when a later pass needs it.

Optimisation passes have different effects on the input code, and I did not provide any functionality for the automatic detection of pass invalidation.
Each pass is therefore responsible on completion for indicating which previously valid passes may have become invalidated.

The list of passes that have or will be invoked is stored in the `Opt.opts` variable, from which invalidated passes may be filtered out.

The `example_analysis` pass is a so-called *analysis* pass, meaning that the pass does not perform any transformations on the code.
Accordingly, its optimisation pass returns `self.opts` without any filtering.

However, the `example_opt` pass actually performs transformations.

> *Note.* It is impossible to know what new optimisation passes may be added to the registry in the future, so it is preferable to make **conservative** judgments on preservation.
>
> For example, returning `[opt for opt in self.opts if opt.ID in (...)]` makes a deliberate choice which passes would be preserved, and is robust against the introduction of new passes that may also be invalidated.
> (Missing out on other passes being preserved hinders efficiency, but correctness takes priority.)

## Managing metadata

Optimisation passes communicate with each other by reading and writing *metadata* for the code.
In source code, metadata is stored in comments, but this information is managed during optimisation via methods inherited from `opt.tools.Opt`.

### Writing metadata

The basic methods for writing metadata are
```python
Opt.assign(cfg_var, *values, append:bool)
Opt.assign(block, block_var, *values, append:bool)
Opt.assign(block, instr_idx:int, instr_var, *values, append:bool)
```
These methods define metavariables at the CFG level, the basic block level, and the instruction level.

The values passed must all be strings.
The boolean `append` keyword argument toggles whether or not this data is to be appended to existing metadata assigned to the particular metavariable, or if the previous data should be cleared and overwritten with these new values.

### Reading metadata

The basic methods for reading metadata are
```python
Opt.get(cfg_var, *, default)
Opt.get(block, block_var, *, default)
Opt.get(block, instr_idx:int, instr_var, *, default)
```
which are dual to the writing methods described above.
Note that the `default` keyword argument (which is returned if the corresponding variable does point to existing metadata) must be assigned to a list of strings if it is assigned at all; the default value is otherwise `None`.

There is also syntactic sugar for when `default=None` is suitable via `__getitem__` and `slice` objects:
```python
Opt[cfg_var]
Opt[block:block_var]
Opt[block:instr_idx:instr_var]
```

However, it is **not** recommended to expose metadata access like this for other passes.
Instead, other `getter` methods should be implemented.
For instance, `example_analysis` implements a few `getter` methods to help other passes interface with its metadata:
```python
class ExampleAnalysis(ExampleAnalysis):
    # ...
    @ExampleAnalysis.getter
    def get_count(self):
        return int(self[f"num_{self.count}"])

    @ExampleAnalysis.getter
    def get_op_indices(self, block):
        return list(map(int, self[block:self.var]))
```

By wrapping these methods with the `getter` decorator, we indicate that these methods rely on the validity of the pass to be valid; if the pass is not valid, then the `opt_pass` method will be invoked prior to the `getter` method call.

These custom methods also have other advantages:
- Unlike the generic metadata `get` call, these methods are visible to Python and its `help` builtin method.
- The generic `get` call either returns `None` or a list of strings, which can be inconvenient if the metadata is meant to represent a single integer, for instance. This can be fixed with custom `getter` methods.

## Debugging

It is likely very helpful (even after the optimisation pass is made to work without error) to litter the optimisation pass with debugging information.

To print to the debugger, call the inherited method
```python
Opt.debug(*args, **kwargs)
```
which is effectively a decorated version of Python's built-in `print` function (and thus behaves similarly), but standardises the output between passes (all of which will be printing to the same debugger).

The debugger is disabled by default by the interpreter `ami.py` and optimiser `amo.py`.
To enable debug output, just pass the `-D` argument:
```console
python3 amo.py --add-pass="pass" -D path/to/code.ami
```

## Bootstrapping off other passes

The previous section describes how to write metadata and read your own metadata.
In order to read metadata from other passes, we use methods automatically inherited from `opt.tools.RequiresOpt`.

To illustrate how to establish a dependence on another pass, consider the `example_opt` pass.
One of its "optimisations" is to swap all addition or multiplication operands (as determined by a command-line argument).
On the other hand, the locations of all addition or multiplication instructions can be determined by the `example_analysis` pass.

Therefore, we can save the effort of finding this information ourselves by relying on this other pass:
```python
class ExampleOpt(ExampleOpt):
    @ExampleOpt.init("example_opt", "add", ...)
    def __init__(self, swap, *, ...)
        self.swap = swap # "add" or "mul"
        # ...
    @ExampleOpt.opt_pass
    def swap_and_trim(self):
        analysis = self.require(ExampleAnalysis, self.swap, count=any)
        # ...
```
The last line assigns `analysis` to the `example_analysis` instance whose positional argument is equal to the `swap` argument of our pass, and the `count` keyword argument can be anything.

This is achieved through the method
```python
RequiresOpt.require(Pass, *args, **kwargs)
```
which scans the existing optimisations (among those that have already been instantiated e.g. by `amo.py`) for an optimisation whose positional and keyword arguments align with the specifications.
If no such pass eists, then a new instance of `Pass` is invoked with the specifid arguments (and the default values for arguments assigned `any`).

Given a pass instance `opt`, we can then fetch its corresponding metadata using the `getter` methods described [earlier](#reading-metadata).
We may also ensure that `opt` has run its optimisation by calling the method `opt.perform_opt()`, which invokes the method decorated with `opt_pass`.

> *Note.* If the pass is already "valid", then calling `opt.perform_opt()` will do nothing.
>
> If a `getter` method is called from the pass and the pass is not valid, the optimisation will be performed automatically at that instant.
> However, it may be safer to explicitly invoke the optimisation in advance (it is also completely required to invoke a transformation pass, since they typically do not write any metadata).
>
> There may be undefined behaviour if a pass is automatically invoked during a `getter` method call if your pass is halfway through a transformation.

To aid in using an existing pass when writing your own, you can view documentation on the pass by running
```console
python3 amo.py --explain-full "pass"
```

## Registering the pass

In order for a pass to actually be used in optimisations, it needs to be registered.
This is managed by `opt.OptManager`.

So, for instance, to register the `example_analysis` pass---which is implemented by the `ExampleAnalysis` class in `opt/example/example_analysis.py` (relative to the root of this repo)---simply write the line

```python
OptManager.register("opt.example.example_analysis.ExampleAnalysis")
```

somewhere near the bottom of `opt/__init__.py`.

> *Note.* The relative position of these registered passes has no bearing on anything.
> If pass IDs are not unique, the `OptManager` will complain.

## Testing

It is important to ensure that any pass is correct, and efficient.
To help do so, we have the `batch_test.py` script.
```console
python3 batch_test.py --add-folder code/folder {test} [test options]
```
the `--add-folder` option to point to a folder for testing (you can pass `--add-folder` multiple times to test multiple folders).
If unspecified, the script will test on the entire `code/` folder.

The option `{test}` is required, and specifies which test to run, which is one of `opt`, `run`, and `stats`.

As usual, running
```console
python3 batch_test.py -h
```
displays all options and their explanations and usage.

### The `opt` test
```console
python3 batch_test.py [...] opt --add-pass="pass"
```

The `opt` flag tells the script to apply optimisation passes to all code in the specified folder(s).
The syntax for passes is the same as for [`amo.py`](amo.md).

The purpose of this test is to ensure that the optimisation at least runs without throwing any errors.

Optimised code for `code/foo/bar.ami` is saved in `code/foo/bar.vfy/` with the name given by the sequence of passes executed.
To delete these folders (without deleting the original `ami` files), run
```console
python3 batch_test.py --clear-vfy
```

The passes given `--add-pass` flags append to the same single optimisation pipeline.
To compile several pipelines (e.g. for testing), use the `--file` flag:
```console
python3 batch_test.py [...] opt --file passes.opt
```
where `passes.opt` might look something like
```
ssa dce branch-elim
gvn-reduce(expr, gvn=scc) dce branch-elim
gvn-reduce(var) reg-realloc
```
This would tell `batch_opt` to run three separate builds, one per line of `passes.opt`.

### The `run` test
```console
python3 batch_test.py [...] run
```

After the `opt` test, `run` checks that the output files have the same input/output behaviour as the original file.
To do so, the `run` test expects sample input data to `code/foo/bar.ami` as `*.in` files in the folder `code/foo/bar.in/`.

The script will first generate test output for each input using the original scripts, storing them in `code/foo/bar.out/`.
The script will likewise generate output for each input applied to the various optimised codes found in `code/foo/bar.vfy/`.

After all of the output is generated, the script will conclude with a pass verifying that the outputs line up, complaining otherwise.

If files disagree, you can see their diff by running
```console
python3 batch_test.py diff code/foo/bar.out/test.out code/foo/bar.vfy/opt.out/test.out
```
(which has pretty and colourful output, or you can just use the usual `diff` command).
> *Note.* The diff output is also saved in `code/foo/bar.vfy/opt.out/test.diff`.

To clear the output folders (but not the optimised code), run
```console
python3 batch_test.py --clear-out
```

To clear all generated files (therefore only keeping the original code and the input files), run
```console
python3 batch_test.py --clear
```

### `stats`

The `run` test generates `diff` files as well as `trace` files, the latter containing the execution path of both the original and optimised programs.
There are two options:
```console
python3 batch_test.py [...] stats code
python3 batch_test.py [...] stats trace
```
The `code` option analyses the effect of the optimisation on code: in particular, it indicates for each program:
- the total number of instructions
- the total number of basic blocks
- the total number of virtual registers
- the number of `phi` nodes
and compares them with each other and the original.

The `trace` option analyses the runtime information.
Since "runtime" is likely not very meaningful (the language is simulated... in Python), it instead indicates for each program and each test input:
- the number of instructions executed
- the number of basic blocks executed (equivalently, the number of branches + 1)
- the number of *conditional* branches executed

The format of the output is controlled by the `--style` option, and can be `pretty`, `csv`, or `latex`.
If you wish to pipe the output into a file, you might want to disable the ANSI colouring, so run e.g.
```console
python3 batch_test.py --plain stats trace --style=csv > stats.csv
```

Other options for `stats` can be found by running
```console
python3 batch_test.py stats -h
```
