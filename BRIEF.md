# FD-258 Card Generator — Project Brief

## Purpose
Generate print-ready blank **FBI FD-258 fingerprint cards** (8"×8" true card size) for
manual ink fingerprinting. A client (e.g. Marcelo Gros) prints the card, takes it to a
fingerprinting station (or rolls their own prints), and the completed card is mailed to
the FBI CJIS Division per the Provn workflow.

## Hard requirements (QA gates — do NOT violate)

1. **Card page size MUST be 576×576 pt = 8"×8"** (true FD-258 card size). `pdfinfo` must
   report `Page size: 576 x 576 pts`.
2. **Embedded raster must be 300 DPI** (2400×2400 px for an 8" card). The 72-DPI downsample
   is a QA FAIL — never produce it. If the card is vector (preferred), it must rasterize
   cleanly to 2400×2400 px @ 300 DPI for the printer.
3. Output must be a single PDF per card, named `FD-258_<LASTNAME>_<FIRSTNAME>.pdf`
   (e.g. `FD-258_GROS_MARCELO.pdf`).
4. A companion `--letter` mode produces a **letter (612×792 pt)** layout embedding the
   card at 100% scale centered, with margins — for printing on standard paper at a
   library/office printer, then trimming to 8×8.
5. The card MUST include the standard FBI FD-258 fields and layout:
   - Header: "FEDERAL BUREAU OF INVESTIGATION" / "UNITED STATES DEPARTMENT OF JUSTICE"
     / "FINGERPRINT CARD"
   - ORI (Originating Agency Identifier) block, OCA block, date
   - Personal data: LAST NAME / FIRST NAME / MIDDLE NAME, ALIASES, RESIDENCE,
     DATE OF BIRTH, SEX, RACE, HEIGHT, WEIGHT, EYES, HAIR, PLACE OF BIRTH,
     SIGNATURE OF PERSON FINGERPRINTED, CONTRIBUTOR'S NAME AND ADDRESS,
     REASON FINGERPRINTED, SIGNATURE OF OFFICIAL TAKING FINGERPRINTS
   - 10 fingerprint blocks (rolled impressions, 5 across × 2 rows) labeled
     RIGHT HAND and LEFT HAND with individual block labels
     (R. THUMB, R. INDEX, ... L. THUMB, ...) and 4-finger simultaneous +
     thumb impression areas at the bottom
   - Boxes/areas must be clean, ink-friendly (not too thin), standard FD-258 proportions
6. CLI:
   - `python fd258_card.py generate --out FD-258_GROS_MARCELO.pdf [--letter]`
     → blank card (fields empty, ready for manual filling)
   - `python fd258_card.py generate --lastname Gros --firstname Marcelo --dob ...`
     → pre-filled card (optional; keep blank by default)
   - `python fd258_card.py verify --file X.pdf` → runs the QA gate:
     pdfinfo page size == 576×576 (or letter 612×792 for --letter), embedded image
     DPI ≥ 300, and prints PASS/FAIL per check. Non-zero exit on any FAIL.

## Technical notes
- Python 3.11, **reportlab** (already installed in the hermes venv at
  `/usr/local/lib/hermes-agent/venv/bin/python`) — use reportlab's canvas/graphics for
  vector drawing (crisp at any DPI; QA gate then checks the PDF's declared resolution
  and, if a raster fallback is used, the embedded image size).
- poppler-utils (`pdfinfo`, `pdfimages`, `pdftotext`) available for the verify step.
- No external network calls. No PII beyond what the operator passes via CLI.
- Keep it dependency-light: reportlab only.

## Deliverables
- `fd258_card.py` (single-file tool, ~600-900 lines, well-commented)
- `README.md` (usage, QA gates, printing instructions incl. 100% scale / "Actual size"
  so the 8×8 card prints true-to-size)
- `tests/test_fd258.py` or a `make verify` target that generates a sample card,
  runs the QA gate, and asserts the three hard requirements
- Sample output: `samples/FD-258_GROS_MARCELO.pdf` (blank, 8×8, 300 DPI) — MUST be
  generated and verified as part of the build

## Context (why this exists)
Provn (getproven.us) is Shah's FBI background-check business. FD-258 cards are mailed
to: FBI CJIS Division, ATTN: ELECTRONIC SUMMARY REQUEST, 1000 Custer Hollow Road,
Clarksburg, WV 26306 — ALWAYS with a copy of the FBI EDO order confirmation email.
This repo automates the blank-card generation half of that packet. The print-readiness
rules above come from a proven 2026-08-11 QA pass (2400×2400px @300 DPI was the
canonical good build; the 576×576 @72ppi build was rejected by Shah as blurry).
