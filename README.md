# FD-258 Card Generator

Generates print-ready, true-size **FBI FD-258 fingerprint cards** — 8" × 8"
(576 × 576 pt) — as single-page PDFs for manual ink fingerprinting.

Part of the [Provn](https://getproven.us) FBI background-check workflow: the
client prints the blank card, has their prints rolled (police station, UPS
Store, mobile printer service), and mails the completed card to CJIS.

```
FBI CJIS Division
ATTN: ELECTRONIC SUMMARY REQUEST
1000 Custer Hollow Road
Clarksburg, WV 26306
```

**Always enclose a copy of the FBI EDO order confirmation email** with the card.

---

## Quick start

```bash
PY=/usr/local/lib/hermes-agent/venv/bin/python     # reportlab lives here

# blank 8x8 card, vector
$PY fd258_card.py generate --out FD-258_GROS_MARCELO.pdf

# blank 8x8 card with a literal 300 DPI (2400x2400 px) embedded rendering
$PY fd258_card.py generate --raster --out FD-258_GROS_MARCELO.pdf

# same card mounted on US Letter at 100% with trim marks
$PY fd258_card.py generate --letter --out FD-258_GROS_MARCELO_letter.pdf

# QA gate (non-zero exit on any FAIL)
$PY fd258_card.py verify --file FD-258_GROS_MARCELO.pdf
```

Or via make:

```bash
make sample     # regenerate samples/FD-258_GROS_MARCELO.pdf (300 DPI) + verify
make verify     # run the QA gate on the sample
make test       # 31 unittest checks, incl. the three hard requirements
make all        # sample + verify + test
```

Shipped sample: [`samples/FD-258_GROS_MARCELO.pdf`](samples/FD-258_GROS_MARCELO.pdf)
— blank, 576 × 576 pt, 2400 × 2400 px @ 300 DPI embedded, QA verified.

---

## CLI

### `generate`

| Flag | Meaning |
|---|---|
| `--out PATH` | output file (default `FD-258_<LASTNAME>_<FIRSTNAME>.pdf`) |
| `--outdir DIR` | directory to write into (created if missing) |
| `--letter` | mount the 8×8 card at 100% on US Letter (612 × 792 pt) with trim marks |
| `--raster` | embed a 300 DPI rendering instead of vector art |
| `--dpi N` | raster resolution for `--raster` (default **and minimum** 300) |
| `--verify` | run the QA gate on the file just written |

Optional pre-fill (the card is **blank by default** — omit these for a card the
client fills in by hand):

`--lastname --firstname --middlename --aliases --residence --citizenship
--dob --sex --race --height --weight --eyes --hair --pob --ssn --date-signed
--contributor --reason --ori --oca --date-fingerprinted`

```bash
$PY fd258_card.py generate \
    --lastname Gros --firstname Marcelo \
    --dob "03 14 1988" --sex M --race W --height 5-11 --weight 175 \
    --eyes BRO --hair BLK --pob "BUENOS AIRES, ARGENTINA" \
    --reason "APPLICANT - FBI IDENTITY HISTORY SUMMARY"
# -> FD-258_GROS_MARCELO.pdf
```

No PII is stored, logged or transmitted: values go straight onto the page and
nothing leaves the machine. The tool makes **no network calls**.

### `verify`

```bash
$PY fd258_card.py verify --file FD-258_GROS_MARCELO.pdf
$PY fd258_card.py verify --file card_letter.pdf --letter
$PY fd258_card.py verify --file card.pdf --no-fields   # skip the label check
```

```
QA gate: samples/FD-258_GROS_MARCELO.pdf
------------------------------------------------------------------------
[PASS] page size == 576 x 576 pts (card 576x576)
       pdfinfo reports 576 x 576 pts, 1 page(s)
[PASS] single page
       1 page(s)
[PASS] embedded raster DPI >= 300
       2400x2400px @ 300x300 dpi
[PASS] rasterises to 2400 x 2400 px @ 300 DPI
       pdftoppm -r 300 gives 2400 x 2400 px
[PASS] required FD-258 fields present
       all 36 labels found
------------------------------------------------------------------------
RESULT: PASS
```

Exit code is `0` only when every check passes, `1` on any FAIL, `2` on a tool
error (e.g. poppler missing).

---

## QA gates

These are the non-negotiable print-readiness rules, from the 2026-08-11 QA pass.

1. **Page size is exactly 576 × 576 pt = 8" × 8".** `pdfinfo` must report
   `Page size: 576 x 576 pts`. In `--letter` mode: `612 x 792 pts`.
2. **300 DPI print readiness.** The page must rasterise to 2400 × 2400 px at
   300 DPI, and any embedded raster must itself be ≥ 300 DPI. The
   576 × 576 px @ 72 ppi downsample — the build rejected as blurry — fails this
   gate, and the test suite asserts that it fails.
3. **One PDF per card**, named `FD-258_<LASTNAME>_<FIRSTNAME>.pdf`.
4. **The FD-258 field inventory is present** (checked via `pdftotext`): masthead,
   ORI/OCA/date, the personal-data block, all ten rolled impression blocks, and
   the simultaneous four-finger + thumb areas.

### Vector vs. `--raster`

| | vector (default) | `--raster` |
|---|---|---|
| content | lines + text, resolution independent | 2400 × 2400 px image @ 300 DPI + invisible text layer |
| `pdfimages -list` | no images (nothing to downsample) | `2400x2400 … 300 300` |
| file size | ~3 KB | ~250 KB |
| use when | you want the sharpest possible print | a print shop / RIP wants an explicit 300 DPI raster |

Both pass the gate. Vector is preferred for printing — it is sharp at *any*
device resolution, not just 300 DPI. The shipped sample uses `--raster` so the
300 DPI figure is stated explicitly inside the PDF; the raster build keeps an
invisible text layer, so the card stays searchable and the field check still
works.

---

## Printing instructions (get this wrong and the card is rejected)

The FBI scans these cards at fixed dimensions. A card printed at 96% is not an
FD-258.

1. Print the **8×8 PDF on 8.5×11 paper** using `--letter` mode, or the plain
   card PDF if your printer accepts custom 8×8 stock.
2. In the print dialog set **Scale: 100%** or **"Actual size"**.
   **Do not** use "Fit to page", "Shrink oversized pages", or "Scale to fit".
   – Acrobat/Preview: *Page Sizing & Handling → Actual Size*
   – Chrome/Edge: *More settings → Scale → Custom → 100*
3. Print on **white card stock, 90–110 lb (≈ 200 gsm)** if you can. Plain paper
   works but smears under fingerprint ink and can be rejected.
4. Use a **laser printer** (inkjet output can smudge when the print roller
   passes over it). Black and white is correct; the card needs no colour.
5. **Trim on the corner marks to exactly 8" × 8"** (letter mode only).
6. Check with a ruler: the outer printed frame is 7.5", the trimmed card is 8.0".
   If it measures short, the print was scaled — reprint at 100%.
7. Fill in with **black ink**, print (don't cursive) all information, and have
   the person sign in the presence of the official taking the prints.

---

## Card layout

```
┌ ORI / OCA / DATE ───┬─ FEDERAL BUREAU OF INVESTIGATION ─┬── LEAVE BLANK ──┐
│                     │  UNITED STATES DEPT. OF JUSTICE   │   (FBI use)     │
│                     │        FINGERPRINT CARD           │                 │
├─────────────────────┴───────────────────────────────────┴─────────────────┤
│ TYPE OR PRINT ALL INFORMATION IN BLACK …                                  │
├──────────────────┬────────────────────┬───────────────────────────────────┤
│ LAST NAME    NAM │ FIRST NAME         │ MIDDLE NAME                       │
│ SIGNATURE OF PERSON FINGERPRINTED     │ ALIASES                       AKA │
│ RESIDENCE                         RES │ COUNTRY OF CITIZENSHIP        CTZ │
│ DOB │ SEX │ RACE │ HGT │ WGT │ EYES │ HAIR │ PLACE OF BIRTH          POB  │
│ SIGNATURE OF OFFICIAL TAKING FINGERPRINTS │ DATE SIGNED │ SOC. SEC. NO.   │
│ CONTRIBUTOR'S NAME AND ADDRESS            │ REASON FINGERPRINTED          │
├───────────────────────────────────────────────────────────────────────────┤
│ RIGHT HAND — rolled impressions                                           │
│ 1. R. THUMB │ 2. R. INDEX │ 3. R. MIDDLE │ 4. R. RING │ 5. R. LITTLE      │
│ LEFT HAND — rolled impressions                                            │
│ 6. L. THUMB │ 7. L. INDEX │ 8. L. MIDDLE │ 9. L. RING │ 10. L. LITTLE     │
│ PLAIN IMPRESSIONS — TAKEN SIMULTANEOUSLY                                  │
│ LEFT FOUR FINGERS │ L. THUMB │ R. THUMB │ RIGHT FOUR FINGERS              │
└───────────────────────────────────────────────────────────────────────────┘
```

Geometry lives in one place at the top of `fd258_card.py` (band heights, field
widths). `_validate_geometry()` runs at import and refuses to load if the bands
no longer sum to the 540 pt content area, so the card can never silently drift
off 8×8; `draw_card()` re-asserts the same thing after drawing.

---

## Requirements

* Python 3.11
* **reportlab** — the only Python dependency
  (`/usr/local/lib/hermes-agent/venv/bin/python` has 5.0.0 installed)
* **poppler-utils** (`pdfinfo`, `pdfimages`, `pdftotext`, `pdftoppm`) — for
  `verify` and for `--raster`

Vector `generate` needs reportlab only; poppler is used by the QA gate and the
raster build.

## Files

| Path | What |
|---|---|
| `fd258_card.py` | the whole tool: layout, generator, QA gate, CLI |
| `tests/test_fd258.py` | 31 checks, one class per hard requirement |
| `Makefile` | `sample` / `verify` / `test` / `all` / `clean` |
| `samples/FD-258_GROS_MARCELO.pdf` | blank 8×8 card, 300 DPI, QA verified |
