PY=PYTHONPATH=. python3
PYI=$(PY) -i

PYTESTS=CFG/basicblocks

TESTS=$(PYTESTS)


.PHONY: $(TESTS:%=test-%) $(PYTESTS:%=interact-%)

$(PYTESTS:%=test-%): test-%: tests/%.py
	@$(PY) $<

$(PYTESTS:%=interact-%): interact-%: tests/%.py
	@$(PYI) $<
