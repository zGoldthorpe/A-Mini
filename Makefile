PY=PYTHONPATH=. python3
PYI=$(PY) -i

CFG=$(patsubst %,CFG/%,\
	basicblocks.py \
	cfg.py)

PARSING=$(patsubst %,parsing/%,\
		reader.py)

TESTS=ensuretypes.py \
	  $(CFG) \
	  $(PARSING)

FOLDERS=CFG parsing

RUNTESTS=$(TESTS:%=tests/%.vfy)
FOLDERTESTS=$(FOLDERS:%=tests/%.vfy)

INTERACT=$(TESTS:%.py=interact/%.py)

.PHONY: $(INTERACT) clean all

all: $(RUNTESTS) $(FOLDERTESTS)

tests/CFG.vfy: $(CFG:%=tests/%.vfy)
	@touch $@

tests/parsing.vfy: $(PARSING:%=tests/%.vfy)
	@touch $@

$(filter %.py.vfy,$(RUNTESTS)): %.py.vfy: %.py
	@$(PY) $<
	@touch $@


$(INTERACT): interact/%.py: tests/%.py
	@$(PYI) $<

clean:
	@rm -f $(RUNTESTS) $(FOLDERTESTS)
