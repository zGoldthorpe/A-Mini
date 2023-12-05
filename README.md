# A-Mi
[![Make Tests](https://github.com/zGoldthorpe/A-Mini/actions/workflows/make.yml/badge.svg)](https://github.com/zGoldthorpe/A-Mini/actions?query=workflow%3A%22Makefile+Tests%22)
[![Opt Tests](https://github.com/zGoldthorpe/A-Mini/actions/workflows/opt.yml/badge.svg)](https://github.com/zGoldthorpe/A-Mini/actions?query=workflow%3A%22Opt+Tests%22)

**A**ssembly-**Mi**nimal: a toy language for experimenting with concepts from the [middle-end](https://en.wikipedia.org/wiki/Compiler#Midle_end) (i.e., optimisations) in a compiler stack.

Sample code can be found in the `code/` folder, which can be executed via the `ami.py` interpreter:
```console
python3 ami.py path/to/code.ami
```
To experiment with optimisation passes, use `amo.py`:
```console
python3 amo.py --add-pass="pass" src.ami -o output.ami
```

## Documentation

1. [About the language](docs/ami.md)
1. [The optimiser](docs/amo.md)
1. [Writing optimisation passes](docs/opt.md)
1. [Control-flow graph visualisation](docs/ami2dot.md)
