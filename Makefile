# Makefile for basic testing
# Produces a *.vfy file on success
# NB: run `make clean` before re-testing a module that has passed before
# (I don't know how to propagate all dependencies so that only necessary *.vfy files get updated)

PY=PYTHONPATH=. python3
PYI=$(PY) -i

CFG=$(patsubst %,CFG/%,\
	basicblocks.py \
	cfg.py)

PARSING=$(patsubst %,parsing/%,\
		reader.py \
		meta.py \
		meta_writer.py)

EXEC=$(patsubst %,execution/%,\
	 	arith.py \
		comp.py \
		branch.py \
		phi.py \
		io.py)

OPT=$(patsubst %,opt/%,\
		 example_analysis.py \
		 abstract_expr.py)

TESTS=ensuretypes.py \
	  $(CFG) \
	  $(PARSING) \
	  $(EXEC) \
	  $(OPT)

FOLDERS=CFG parsing execution opt

RUNTESTS=$(TESTS:%=tests/%.vfy)
FOLDERTESTS=$(FOLDERS:%=tests/%.vfy)

INTERACT=$(TESTS:%.py=interact/%.py)

.PHONY: $(INTERACT) clean all

all: $(RUNTESTS) $(FOLDERTESTS)

tests/CFG.vfy: $(CFG:%=tests/%.vfy)
	@touch $@

tests/parsing.vfy: $(PARSING:%=tests/%.vfy)
	@touch $@

tests/execution.vfy: $(EXEC:%=tests/%.vfy)
	@touch $@

tests/opt.vfy: $(VERIFY:%=tests/%.vfy)
	@touch $@

$(filter %.py.vfy,$(RUNTESTS)): %.py.vfy: %.py
	@$(PY) $<
	@touch $@


$(INTERACT): interact/%.py: tests/%.py
	@$(PYI) $<

clean:
	@rm -f $(RUNTESTS) $(FOLDERTESTS)
