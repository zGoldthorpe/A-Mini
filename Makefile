PY=PYTHONPATH=. python3
PYI=$(PY) -i

CFG=$(patsubst %,CFG/%,\
	basicblocks.py \
	cfg.py)

TESTS=ensuretypes.py \
	  $(CFG)

FOLDERS=CFG

RUNTESTS=$(TESTS:%=tests/%.vfy)
FOLDERTESTS=$(FOLDERS:%=tests/%.vfy)

INTERACT=$(TESTS:%.py=interact/%.py)

.PHONY: $(INTERACT) clean echo

echo:
	@echo $(TESTS)
	@echo $(RUNTESTS)

tests/CFG.vfy: $(CFG:%=tests/%.vfy)
	@touch $@

$(filter %.py.vfy,$(RUNTESTS)): %.py.vfy: %.py
	@$(PY) $<
	@touch $@


$(INTERACT): interact/%.py: tests/%.py
	@$(PYI) $<

clean:
	@rm -f $(RUNTESTS) $(FOLDERTESTS)
