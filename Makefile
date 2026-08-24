# FD-258 card generator — build, sample and QA gate.
#
#   make sample   regenerate samples/FD-258_GROS_MARCELO.pdf (300 DPI)
#   make verify   run the QA gate against the sample (non-zero exit on FAIL)
#   make test     run the full unittest suite
#   make all      sample + verify + test
#   make clean    remove build artefacts

PYTHON ?= /usr/local/lib/hermes-agent/venv/bin/python
TOOL   := fd258_card.py
SAMPLE := samples/FD-258_GROS_MARCELO.pdf

.PHONY: all sample verify test clean

all: sample verify test

# Blank 8x8 card with a literal 300 DPI (2400x2400 px) embedded rendering.
sample: $(SAMPLE)

$(SAMPLE): $(TOOL)
	$(PYTHON) $(TOOL) generate --raster --outdir samples \
		--out FD-258_GROS_MARCELO.pdf --verify

# The QA gate: page size 576x576 pt, >= 300 DPI, required FD-258 fields.
verify: $(SAMPLE)
	$(PYTHON) $(TOOL) verify --file $(SAMPLE)

test:
	$(PYTHON) -m unittest discover -s tests -t . -v

clean:
	rm -rf build __pycache__ tests/__pycache__ FD-258_*.pdf
