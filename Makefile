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

TESTS=ensuretypes.py \
	  $(CFG) \
	  $(PARSING) \
	  $(EXEC)

FOLDERS=CFG parsing execution

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

$(filter %.py.vfy,$(RUNTESTS)): %.py.vfy: %.py
	@$(PY) $<
	@touch $@


$(INTERACT): interact/%.py: tests/%.py
	@$(PYI) $<

clean:
	@rm -f $(RUNTESTS) $(FOLDERTESTS)
