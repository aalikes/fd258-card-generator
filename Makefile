# Official FBI FD-258 card generator — build, sample and QA gate.
#
#   make fetch    refresh official/fd-258-official-fillable.pdf from fbi.gov
#   make sample   regenerate samples/FD-258_GROS_MARCELO.pdf from the official card
#   make verify   run the QA gate against the sample (non-zero exit on FAIL)
#   make test     run the full unittest suite
#   make all      sample + verify + test
#   make clean    remove build artefacts

PYTHON   ?= /usr/local/lib/hermes-agent/venv/bin/python
TOOL     := fd258_card.py
SAMPLE   := samples/FD-258_GROS_MARCELO.pdf
OFFICIAL := official/fd-258-official-fillable.pdf

.PHONY: all fetch sample verify test clean

all: sample verify test

# Re-download the official card published by the FBI.
fetch:
	$(PYTHON) $(TOOL) fetch

# The official FD-258 as published: blank, both pages, 8x8 (576x576 pt).
sample: $(SAMPLE)

$(SAMPLE): $(TOOL) $(OFFICIAL)
	$(PYTHON) $(TOOL) generate --outdir samples \
		--out FD-258_GROS_MARCELO.pdf --verify

# The QA gate: 576x576 pt, 2 pages, >= 300 DPI, official FBI markers + labels.
verify: $(SAMPLE)
	$(PYTHON) $(TOOL) verify --file $(SAMPLE)

test:
	$(PYTHON) -m unittest discover -s tests -t . -v

clean:
	rm -rf build __pycache__ tests/__pycache__ FD-258_*.pdf
