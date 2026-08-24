# Rework brief: FD-258 card generator must use the OFFICIAL FBI card

## The problem (user correction, 2026-08-24)
The repo currently DRAWS an FD-258 card from scratch with reportlab (vector). That is
WRONG. Shah's correction: "the official FD-258 card should be taken from the FBI
website now generated" — the FBI website now generates the official FD-258 card, and
we must use THAT card, not a hand-drawn approximation.

## Source of truth (verified live)
- Official FBI FD-258: https://www.fbi.gov/file-repository/cjis/fd-258.pdf
  (HTTP 200, application/pdf, 1,057,305 bytes, filename FD-258fillable.pdf)
- Already downloaded to: /root/fd258-card-generator/official/fd-258-official-fillable.pdf
- Properties: 2 pages, page size 576×576 pt (true 8"×8" card), AcroForm
  (PDFfiller-flattened; only "ORI" is a live /Tx field — do NOT rely on native
  AcroForm fill), page 1 = APPLICANT card (fields + fingerprint blocks), page 2 =
  "FEDERAL BUREAU OF INVESTIGATION / UNITED STATES DEPARTMENT OF JUSTICE" back with
  usage instructions + print-pattern diagrams. Card marker strings on page 1:
  "FD-258 (Rev. 10/31/2023)" and "OMB No. 1110-0046 (Exp.05/31/2028)".

## What to rework in /root/fd258-card-generator
1. **`generate`**: output the OFFICIAL FBI card, not a drawing.
   - Default: ship the official card PDF as-is (both pages, true 8"×8" = 576×576 pt).
     Copy from the local `official/` cache; if missing, download from the fbi.gov URL.
   - Optional pre-fill (--lastname/--firstname/--dob etc.): the official PDF is
     effectively flat, so pre-fill = TEXT OVERLAY on page 1 at the correct field
     coordinates (LAST NAME / FIRST NAME / MIDDLE NAME / DOB / SEX / RACE / HEIGHT /
     WEIGHT / EYES / HAIR / PLACE OF BIRTH / RESIDENCE / OCA etc.) via a pypdf
     + reportlab overlay. Keep blank-by-default behavior (manual ink workflow).
     If coordinates can't be determined reliably, document that blank is the safe
     default and pre-fill is best-effort.
   - `--letter` mode: official card mounted on US Letter (612×792) at 100% scale with
     trim marks for standard-paper printing then trim to 8×8.
2. **`verify`**: QA gates must now prove it's the OFFICIAL card:
   - page size 576×576 pt (or 612×792 for letter mode) — KEEP
   - embedded raster ≥ 300 DPI (2400×2400 px) for print — KEEP (render the official
     card's pages to 300 DPI if needed for the check; the source PDF itself is vector
     text — verify against page size + text markers + a 300-DPI render check)
   - **NEW: text markers must include "FD-258 (Rev. 10/31/2023)" or "OMB No. 1110-0046"
     AND "FEDERAL BUREAU OF INVESTIGATION" — proves it is the official FBI card**
   - non-zero exit on any FAIL — KEEP
3. **Samples**: regenerate `samples/FD-258_GROS_MARCELO.pdf` FROM THE OFFICIAL CARD
   (blank, both pages, 8×8) and pass verify.
4. **README**: document the official-source workflow (fbi.gov URL, local cache,
   why we no longer draw from scratch, printing instructions at 100%/Actual size).
5. **Tests**: update to the new behavior — tests must assert the output comes from the
   official card (text markers) and still meets 576×576 + 300 DPI.

## Constraints
- Python 3.11; use the hermes venv python: /usr/local/lib/hermes-agent/venv/bin/python
  (reportlab 5.0.0 + pypdf are installed there now; poppler-utils pdfinfo/pdfimages/
  pdftotext available).
- Do NOT lose the CLI shape (generate / verify / --out / --letter / --lastname /
  --firstname). Existing callers use it.
- The official PDF stays at official/fd-258-official-fillable.pdf as the bundled
  cache; generate falls back to downloading from the fbi.gov URL if missing.
- Keep it dependency-light.

## Definition of done
- `python fd258_card.py generate --lastname Gros --firstname Marcelo --out /tmp/official-test.pdf`
  produces the official 2-page card (576×576 pt, text markers present).
- `python fd258_card.py verify --file /tmp/official-test.pdf` prints PASS for all gates.
- samples/FD-258_GROS_MARCELO.pdf regenerated + verified.
- `make test` green.
- README updated to say the card is the official FBI-generated FD-258 from fbi.gov.
