#!/usr/bin/env python3
"""
fd258_card.py — print-ready **official** FBI FD-258 fingerprint card generator.

This tool does not draw an FD-258.  It ships the *official* FD-258 that the FBI
publishes on fbi.gov, byte-for-byte, and (optionally) lays typed values on top
of it.  The card is a true-size 8" x 8" (576 x 576 pt) two-page PDF — page 1 is
the APPLICANT card, page 2 is the FBI/DOJ back with the usage instructions and
the print-pattern diagrams — ready for manual ink fingerprinting and mailing to:

    FBI CJIS Division
    ATTN: ELECTRONIC SUMMARY REQUEST
    1000 Custer Hollow Road
    Clarksburg, WV 26306

(Always mail the card together with a copy of the FBI EDO order confirmation
email.)

Source of truth
---------------
* Official PDF: https://www.fbi.gov/file-repository/cjis/fd-258.pdf
  (served as ``FD-258fillable.pdf``).  A copy is bundled at
  ``official/fd-258-official-fillable.pdf``; ``generate`` uses that cache and
  falls back to downloading from fbi.gov when it is missing.
* The published PDF has been flattened by PDFfiller — only ``ORI`` survives as
  a live AcroForm text field — so pre-fill is done as a **text overlay** at the
  official field coordinates (pypdf + reportlab), never via form filling.
* Blank remains the default: the manual ink workflow wants an empty card.

Modes
-----
* default   the official card as published, both pages, 576 x 576 pt.
* --letter  each official page mounted at **100% scale** on US Letter
            (612 x 792 pt) with trim marks, for printing on standard paper and
            trimming down to 8" x 8".
* --raster  each official page re-rendered through poppler at 300 DPI (2400 x
            2400 px) and embedded 1:1, plus an invisible text layer rebuilt
            from the original word boxes so the card stays searchable and the
            QA gate's text checks keep working.

Dependencies: pypdf + reportlab (poppler-utils pdfinfo/pdfimages/pdftotext/
pdftoppm for ``verify``, ``--raster`` and the invisible text layer).
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET

from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.colors import Color, black
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as rl_canvas

# --------------------------------------------------------------------------- #
# Page / card geometry  (all values in PostScript points, 72 pt == 1 inch)
# --------------------------------------------------------------------------- #

PT_PER_INCH = 72.0

CARD_SIZE = 576.0                     # 8.00 in  -> the official card's page size
LETTER_W, LETTER_H = 612.0, 792.0     # US Letter mounting

PRINT_DPI = 300
CARD_PX_AT_300 = int(round(CARD_SIZE / PT_PER_INCH * PRINT_DPI))   # == 2400

# Where the 8x8 card sits on the Letter sheet: centred, unscaled (100%).
LETTER_OX = (LETTER_W - CARD_SIZE) / 2.0        # 18 pt
LETTER_OY = (LETTER_H - CARD_SIZE) / 2.0        # 108 pt

OFFICIAL_PAGES = 2                    # APPLICANT card + FBI/DOJ back

# --------------------------------------------------------------------------- #
# The official card
# --------------------------------------------------------------------------- #

OFFICIAL_URL = "https://www.fbi.gov/file-repository/cjis/fd-258.pdf"
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
OFFICIAL_CACHE = os.path.join(REPO_DIR, "official", "fd-258-official-fillable.pdf")
OFFICIAL_MIN_BYTES = 200_000          # the real file is ~1.0 MB; anything tiny is an error page

# Strings that only the genuine FBI-published FD-258 carries.  The QA gate
# proves provenance with these.
MARKER_REVISION = "FD-258 (Rev. 10/31/2023)"
MARKER_OMB = "OMB No. 1110-0046"
MARKER_AGENCY = "FEDERAL BUREAU OF INVESTIGATION"


def official_card_path(cache: str = OFFICIAL_CACHE,
                       allow_download: bool = True) -> str:
    """
    Return a path to the official FD-258 PDF.

    Uses the bundled ``official/`` cache; downloads it from fbi.gov when the
    cache is missing (or is too small to be the real document).
    """
    if os.path.isfile(cache) and os.path.getsize(cache) >= OFFICIAL_MIN_BYTES:
        return cache
    if not allow_download:
        raise RuntimeError(
            f"official FD-258 not cached at {cache} and downloading is disabled")
    return download_official_card(cache)


def download_official_card(dest: str = OFFICIAL_CACHE,
                           url: str = OFFICIAL_URL) -> str:
    """Fetch the official FD-258 from fbi.gov into `dest` (atomically)."""
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "fd258_card.py"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = resp.read()
    except Exception as exc:                       # network, DNS, TLS, HTTP...
        raise RuntimeError(
            f"could not download the official FD-258 from {url}: {exc}. "
            f"Place the file at {dest} manually and retry.") from exc

    if not payload.startswith(b"%PDF") or len(payload) < OFFICIAL_MIN_BYTES:
        raise RuntimeError(f"{url} did not return a PDF "
                           f"({len(payload)} bytes, header {payload[:8]!r})")

    tmp = dest + ".part"
    with open(tmp, "wb") as fh:
        fh.write(payload)
    os.replace(tmp, dest)
    return dest


# --------------------------------------------------------------------------- #
# Pre-fill overlay geometry
# --------------------------------------------------------------------------- #
# Coordinates were measured off the official page 1 with ``pdftotext -bbox``,
# so they are expressed the way that tool reports them: **origin top-left, y
# growing downwards**, in points on the 576 x 576 page.  ``_field_xy`` flips
# them into reportlab's bottom-left space.
#
# Each entry is (x, y_from_top_of_baseline, max_width, font_size).  Signature
# boxes are deliberately absent: they have to be signed by hand, in ink, in the
# presence of the official taking the prints.

OVERLAY_FIELDS: dict[str, tuple[float, float, float, float]] = {
    # name row
    "lastname":            (227.0,  40.0,  84.0, 8.0),
    "firstname":           (316.0,  40.0,  75.0, 8.0),
    "middlename":          (396.0,  40.0,  47.0, 8.0),
    # aliases / ORI row
    "aliases":             (219.0,  62.0,  92.0, 7.5),
    "ori":                 (330.0,  62.0, 108.0, 8.0),
    # residence block
    "residence":           (  8.0,  90.0, 200.0, 8.0),
    # descriptors row
    "citizenship":         (222.0, 107.0,  88.0, 7.5),
    "sex":                 (330.0, 107.0,  14.0, 7.5),
    "race":                (348.0, 107.0,  22.0, 7.5),
    "height":              (375.0, 107.0,  25.0, 7.5),
    "weight":              (405.0, 107.0,  25.0, 7.5),
    "eyes":                (435.0, 107.0,  23.0, 7.5),
    "hair":                (463.0, 107.0,  21.0, 7.5),
    "pob":                 (490.0, 107.0,  82.0, 7.5),
    # date of birth (Month / Day / Year)
    "dob":                 (490.0,  89.0,  82.0, 8.0),
    # date fingerprinted (the DATE box beside the official's signature)
    "date_fingerprinted":  (  7.0, 122.0,  30.0, 7.0),
    # right-hand admin column
    "oca":                 (222.0, 127.0,  95.0, 8.0),
    "ssn":                 (222.0, 186.0,  95.0, 8.0),
    # left-hand free-text blocks
    "employer":            (  8.0, 145.0, 200.0, 8.0),
    "reason":              (  8.0, 186.0, 200.0, 8.0),
}

# CLI keys that are written into another field's box on the official card.
# (The pre-official tool called the employer block "contributor", and the
# official card has one DATE box rather than separate signed/fingerprinted
# dates -- keep both spellings working for existing callers.)
FIELD_ALIASES = {
    "contributor": "employer",
    "date_signed": "date_fingerprinted",
}

# Every data key the CLI accepts.
DATA_KEYS = list(OVERLAY_FIELDS) + list(FIELD_ALIASES)

F_VALUE = "Helvetica"
F_HEAD = "Helvetica-Bold"
F_LABEL = "Helvetica"
GREY = Color(0.45, 0.45, 0.45)

CJIS_ADDRESS = ("FBI CJIS Division, ATTN: ELECTRONIC SUMMARY REQUEST, "
                "1000 Custer Hollow Road, Clarksburg, WV 26306")


def resolve_data(data: dict | None) -> dict:
    """Fold alias keys onto the official card's field names."""
    resolved: dict[str, str] = {}
    for key, value in (data or {}).items():
        if not value:
            continue
        resolved.setdefault(FIELD_ALIASES.get(key, key), str(value))
    return {k: v for k, v in resolved.items() if k in OVERLAY_FIELDS}


def _field_xy(x: float, y_from_top: float,
              ox: float = 0.0, oy: float = 0.0) -> tuple[float, float]:
    """Top-left-origin card coordinates -> reportlab page coordinates."""
    return ox + x, oy + CARD_SIZE - y_from_top


# --------------------------------------------------------------------------- #
# Small drawing helpers
# --------------------------------------------------------------------------- #

def fit_size(text: str, font: str, size: float, max_w: float,
             min_size: float = 3.2) -> float:
    """Shrink `size` until `text` fits in `max_w` (never below `min_size`)."""
    while size > min_size and pdfmetrics.stringWidth(text, font, size) > max_w:
        size -= 0.25
    return size


def draw_fitted(c: rl_canvas.Canvas, x: float, y: float, text: str, font: str,
                size: float, max_w: float, align: str = "left",
                mode: int = 0) -> None:
    """Draw `text` at baseline `y`, auto-shrinking so it never overflows."""
    if not text:
        return
    size = fit_size(text, font, size, max_w)
    c.setFont(font, size)
    if align == "center":
        c.drawCentredString(x, y, text, mode=mode)
    elif align == "right":
        c.drawRightString(x, y, text, mode=mode)
    else:
        c.drawString(x, y, text, mode=mode)


def draw_prefill(c: rl_canvas.Canvas, data: dict,
                 ox: float = 0.0, oy: float = 0.0) -> None:
    """Lay the typed values over the official card placed at (ox, oy)."""
    c.setFillColor(black)
    for key, value in resolve_data(data).items():
        fx, fy, max_w, size = OVERLAY_FIELDS[key]
        x, y = _field_xy(fx, fy, ox, oy)
        draw_fitted(c, x, y, value, F_VALUE, size, max_w)


# --------------------------------------------------------------------------- #
# Letter-mode furniture
# --------------------------------------------------------------------------- #

def _trim_marks(c: rl_canvas.Canvas, ox: float, oy: float) -> None:
    """Corner crop marks around an 8x8 card placed at (ox, oy)."""
    c.setLineWidth(0.5)
    c.setStrokeColor(black)
    off, ln = 4.0, 10.0
    for cx, sx in ((ox, -1), (ox + CARD_SIZE, 1)):
        for cy, sy in ((oy, -1), (oy + CARD_SIZE, 1)):
            c.line(cx + sx * off, cy, cx + sx * (off + ln), cy)
            c.line(cx, cy + sy * off, cx, cy + sy * (off + ln))


def _letter_notes(c: rl_canvas.Canvas, ox: float, oy: float,
                  page_index: int) -> None:
    """Printing instructions above the card, mailing note below it."""
    cx = LETTER_W / 2.0
    side = "FRONT (APPLICANT CARD)" if page_index == 0 else "BACK (INSTRUCTIONS)"
    c.setFillColor(black)
    draw_fitted(c, cx, oy + CARD_SIZE + 62.0,
                f"OFFICIAL FBI FD-258 — {side} — PRINT AT 100% "
                "(\"ACTUAL SIZE\"), THEN TRIM ON THE MARKS TO 8\" × 8\"",
                F_HEAD, 8.5, LETTER_W - 72.0, align="center")
    c.setFillColor(GREY)
    draw_fitted(c, cx, oy + CARD_SIZE + 50.0,
                "Do not select \"Fit to page\" / \"Shrink oversized pages\" "
                "— scaling breaks the card's true size.",
                F_LABEL, 7.0, LETTER_W - 72.0, align="center")
    draw_fitted(c, cx, oy - 44.0, "Mail the completed card to:  " + CJIS_ADDRESS,
                F_LABEL, 7.0, LETTER_W - 72.0, align="center")
    draw_fitted(c, cx, oy - 56.0,
                "Always enclose a copy of the FBI EDO order confirmation email.",
                F_LABEL, 7.0, LETTER_W - 72.0, align="center")
    c.setFillColor(black)


# --------------------------------------------------------------------------- #
# PDF builders
# --------------------------------------------------------------------------- #

def _set_metadata(writer: PdfWriter, title: str) -> None:
    writer.add_metadata({
        "/Title": title,
        "/Author": "fd258_card.py",
        "/Subject": "Official FBI FD-258 fingerprint card, 8x8 in, print at 100%",
        "/Creator": "fd258_card.py (official card from fbi.gov)",
    })


def _furniture_pdf(data: dict | None, letter: bool, pages: int) -> PdfReader:
    """
    Build the in-memory overlay that goes *on top of* the official pages:
    typed pre-fill values on page 1, plus trim marks and printing notes in
    --letter mode.  Returns a reader with exactly `pages` pages.
    """
    buf = io.BytesIO()
    page_w, page_h = (LETTER_W, LETTER_H) if letter else (CARD_SIZE, CARD_SIZE)
    ox, oy = (LETTER_OX, LETTER_OY) if letter else (0.0, 0.0)
    c = rl_canvas.Canvas(buf, pagesize=(page_w, page_h))
    for i in range(pages):
        if letter:
            _trim_marks(c, ox, oy)
            _letter_notes(c, ox, oy, i)
        if i == 0 and data:
            draw_prefill(c, data, ox, oy)
        c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf)


def build_official_pdf(path: str, data: dict | None = None,
                       letter: bool = False, source: str | None = None) -> str:
    """
    Write the official FD-258 to `path`.

    With no `data` and no `letter`, the official pages are passed through
    unchanged — the output *is* the FBI's card.  `data` adds a text overlay on
    page 1; `letter` mounts each page at 100% on US Letter with trim marks.
    """
    src = source or official_card_path()
    data = resolve_data(data)

    if letter:
        # Fresh Letter sheets with the official page dropped on unscaled.
        writer = PdfWriter()
        for page in PdfReader(src).pages:
            sheet = writer.add_blank_page(width=LETTER_W, height=LETTER_H)
            sheet.merge_transformed_page(
                page, Transformation().translate(LETTER_OX, LETTER_OY))
    else:
        # Pass the official pages through untouched.
        writer = PdfWriter(clone_from=src)

    if data or letter:
        furniture = _furniture_pdf(data, letter, len(writer.pages))
        for page, extra in zip(writer.pages, furniture.pages):
            page.merge_page(extra)

    _set_metadata(writer, "Official FBI FD-258 Fingerprint Card"
                          + (" (US Letter)" if letter else ""))
    with open(path, "wb") as fh:
        writer.write(fh)
    return path


def _word_boxes(pdf: str, page: int) -> list[tuple[float, float, float, float, str]]:
    """
    Word boxes of `page` (1-based) as (xMin, yMin, xMax, yMax, text), in points
    with a top-left origin, straight from ``pdftotext -bbox``.
    """
    require_tool("pdftotext")
    xml = run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), pdf, "-"])
    root = ET.fromstring(xml)
    boxes = []
    for word in root.iter():
        if not word.tag.endswith("word") or not (word.text or "").strip():
            continue
        a = word.attrib
        boxes.append((float(a["xMin"]), float(a["yMin"]),
                      float(a["xMax"]), float(a["yMax"]), word.text.strip()))
    return boxes


def _draw_text_layer(c: rl_canvas.Canvas, pdf: str, page: int,
                     ox: float, oy: float) -> None:
    """
    Redraw a page's words invisibly (PDF text render mode 3) at their original
    positions, so a rasterised build stays searchable and the QA gate's text
    checks behave exactly as they do on the vector card.
    """
    c.setFillColor(black)
    for x0, y0, x1, y1, text in _word_boxes(pdf, page):
        size = max(y1 - y0, 1.0)
        x, y = _field_xy(x0, y1, ox, oy)
        draw_fitted(c, x, y, text, F_VALUE, size, max(x1 - x0, 1.0), mode=3)


def build_raster_pdf(path: str, data: dict | None = None, letter: bool = False,
                     dpi: int = PRINT_DPI, source: str | None = None) -> str:
    """
    Render the official card through poppler at `dpi` and embed the bitmaps at
    1:1 page scale, so the PDF carries a *literal* `dpi` raster (``pdfimages
    -list`` reports it).  `dpi` below 300 is refused: a 72-DPI downsample is the
    exact regression the QA gate exists to catch.
    """
    if dpi < PRINT_DPI:
        raise ValueError(f"--dpi must be >= {PRINT_DPI} (got {dpi}); "
                         "anything lower fails the QA gate")
    require_tool("pdftoppm")
    src = source or official_card_path()
    page_w, page_h = (LETTER_W, LETTER_H) if letter else (CARD_SIZE, CARD_SIZE)
    ox, oy = (LETTER_OX, LETTER_OY) if letter else (0.0, 0.0)
    data = resolve_data(data)

    with tempfile.TemporaryDirectory() as tmp:
        stem = os.path.join(tmp, "page")
        run(["pdftoppm", "-r", str(dpi), "-png", "-gray", "-aa", "yes",
             "-aaVector", "yes", src, stem])
        pngs = sorted(f for f in os.listdir(tmp) if f.endswith(".png"))
        if not pngs:
            raise RuntimeError("pdftoppm produced no output")

        c = rl_canvas.Canvas(path, pagesize=(page_w, page_h))
        c.setTitle(f"Official FBI FD-258 Fingerprint Card ({dpi} DPI)")
        c.setAuthor("fd258_card.py")
        c.setCreator("fd258_card.py (official card from fbi.gov)")
        for i, png in enumerate(pngs):
            # N px across (CARD_SIZE / 72) in  =>  exactly `dpi` DPI.
            c.drawImage(os.path.join(tmp, png), ox, oy,
                        width=CARD_SIZE, height=CARD_SIZE)
            _draw_text_layer(c, src, i + 1, ox, oy)
            if letter:
                _trim_marks(c, ox, oy)
                _letter_notes(c, ox, oy, i)
            if i == 0 and data:
                draw_prefill(c, data, ox, oy)
            c.showPage()
        c.save()
    return path


# --------------------------------------------------------------------------- #
# Shell helpers
# --------------------------------------------------------------------------- #

def run(cmd: list[str]) -> str:
    """Run a command, returning stdout; raise with stderr on failure."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed ({proc.returncode}): "
                           f"{proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"required tool '{name}' not found "
                           "(install poppler-utils)")


# --------------------------------------------------------------------------- #
# QA gate (verify)
# --------------------------------------------------------------------------- #

def pdf_page_size(path: str) -> tuple[float, float, int]:
    """Return (width_pt, height_pt, page_count) as reported by pdfinfo."""
    require_tool("pdfinfo")
    out = run(["pdfinfo", path])
    m = re.search(r"Page size:\s*([\d.]+)\s*x\s*([\d.]+)\s*pts", out)
    if not m:
        raise RuntimeError("pdfinfo did not report a page size")
    pages = re.search(r"Pages:\s*(\d+)", out)
    return float(m.group(1)), float(m.group(2)), int(pages.group(1)) if pages else 0


def embedded_image_dpi(path: str) -> list[tuple[int, int, int, int]]:
    """Return [(width_px, height_px, x_ppi, y_ppi), ...] for embedded rasters."""
    require_tool("pdfimages")
    out = run(["pdfimages", "-list", path])
    rows = []
    for line in out.splitlines()[2:]:
        parts = line.split()
        if len(parts) < 16 or not parts[0].isdigit():
            continue
        try:
            rows.append((int(parts[3]), int(parts[4]),
                         int(float(parts[-4])), int(float(parts[-3]))))
        except ValueError:
            continue
    return rows


def raster_dimensions(path: str, dpi: int = PRINT_DPI) -> tuple[int, int]:
    """Rasterise page 1 at `dpi` with poppler and return its pixel size."""
    require_tool("pdftoppm")
    with tempfile.TemporaryDirectory() as tmp:
        stem = os.path.join(tmp, "probe")
        run(["pdftoppm", "-r", str(dpi), "-f", "1", "-l", "1", path, stem])
        ppms = sorted(os.listdir(tmp))
        if not ppms:
            raise RuntimeError("pdftoppm produced no output")
        return ppm_size(os.path.join(tmp, ppms[0]))


def ppm_size(path: str) -> tuple[int, int]:
    """Parse a binary PPM/PGM header (no image library needed)."""
    with open(path, "rb") as fh:
        head = fh.read(64)
    tokens, i = [], 2                      # skip the "P6" / "P5" magic
    while len(tokens) < 2 and i < len(head):
        ch = head[i:i + 1]
        if ch == b"#":                      # comment: skip to end of line
            while i < len(head) and head[i:i + 1] not in (b"\n", b"\r"):
                i += 1
        elif ch.isdigit():
            j = i
            while j < len(head) and head[j:j + 1].isdigit():
                j += 1
            tokens.append(int(head[i:j]))
            i = j
        else:
            i += 1
    if len(tokens) < 2:
        raise RuntimeError(f"cannot parse raster header of {path}")
    return tokens[0], tokens[1]


# Labels printed on the official FD-258 (page 1 front, page 2 back).
REQUIRED_TEXT = [
    "APPLICANT",
    "TYPE OR PRINT ALL INFORMATION IN BLACK",
    "LEAVE BLANK",
    "LAST NAME", "NAM", "FIRST NAME", "MIDDLE NAME",
    "SIGNATURE OF PERSON FINGERPRINTED",
    "ALIASES", "AKA",
    "RESIDENCE OF PERSON FINGERPRINTED",
    "CITIZENSHIP", "CTZ",
    "SEX", "RACE", "HGT.", "WGT.", "EYES", "HAIR",
    "DATE OF BIRTH", "DOB", "PLACE OF BIRTH", "POB",
    "SIGNATURE OF OFFICIAL TAKING FINGERPRINTS",
    "YOUR NO.", "OCA",
    "UNIVERSAL CONTROL NO.", "UCN",
    "ARMED FORCES NO.", "MNU",
    "SOCIAL SECURITY NO.", "SOC",
    "MISCELLANEOUS NO.",
    "EMPLOYER AND ADDRESS",
    "REASON FINGERPRINTED",
    "R. THUMB", "R. INDEX", "R. MIDDLE", "R. RING", "R. LITTLE",
    "L. THUMB", "L. INDEX", "L. MIDDLE", "L. RING", "L. LITTLE",
    "LEFT FOUR FINGERS TAKEN SIMULTANEOUSLY",
    "RIGHT FOUR FINGERS TAKEN SIMULTANEOUSLY",
    "UNITED STATES DEPARTMENT OF JUSTICE",
]


def pdf_text(path: str) -> str:
    require_tool("pdftotext")
    return run(["pdftotext", "-layout", path, "-"])


def _norm(text: str) -> str:
    return " ".join(text.split()).upper()


def verify_pdf(path: str, letter: bool = False,
               check_fields: bool = True) -> tuple[bool, list[tuple[str, bool, str]]]:
    """
    Run the QA gate.  Returns (all_passed, [(check_name, passed, detail), ...]).

    Gate 1  page size is exactly 576x576 pt (or 612x792 pt in --letter mode)
    Gate 2  both official pages are present (front + back)
    Gate 3  300 DPI print readiness:
              * if the PDF embeds rasters, every one must be >= 300 DPI
                (this is what rejects the blurry 72-ppi build), and
              * the page must rasterise to the expected 300-DPI pixel size
    Gate 4  the official-card provenance markers are present -- this is what
            proves the output came from the FBI's own FD-258 and is not a
            hand-drawn approximation
    Gate 5  the official FD-258 field labels are present (optional)
    """
    results: list[tuple[str, bool, str]] = []
    exp_w, exp_h = (LETTER_W, LETTER_H) if letter else (CARD_SIZE, CARD_SIZE)
    label = "letter 612x792" if letter else "official card 576x576"

    if not os.path.isfile(path):
        return False, [("file exists", False, f"{path} not found")]

    # --- Gate 1: page size ------------------------------------------------
    w, h, pages = pdf_page_size(path)
    ok = abs(w - exp_w) < 0.5 and abs(h - exp_h) < 0.5
    results.append((f"page size == {int(exp_w)} x {int(exp_h)} pts ({label})",
                    ok, f"pdfinfo reports {w:g} x {h:g} pts, {pages} page(s)"))

    # --- Gate 2: both official pages --------------------------------------
    results.append((f"{OFFICIAL_PAGES} pages (official front + back)",
                    pages == OFFICIAL_PAGES, f"{pages} page(s)"))

    # --- Gate 3a: embedded raster resolution ------------------------------
    images = embedded_image_dpi(path)
    if images:
        worst = min(min(x, y) for _, _, x, y in images)
        detail = "; ".join(f"{iw}x{ih}px @ {xp}x{yp} dpi"
                           for iw, ih, xp, yp in images)
        results.append((f"embedded raster DPI >= {PRINT_DPI}",
                        worst >= PRINT_DPI, detail))
    else:
        results.append((f"embedded raster DPI >= {PRINT_DPI}", True,
                        "no embedded rasters - the official card is vector "
                        "text/line art (resolution independent)"))

    # --- Gate 3b: 300-DPI rasterisation -----------------------------------
    px_w, px_h = raster_dimensions(path, PRINT_DPI)
    want_w = int(round(exp_w / PT_PER_INCH * PRINT_DPI))
    want_h = int(round(exp_h / PT_PER_INCH * PRINT_DPI))
    ok = abs(px_w - want_w) <= 1 and abs(px_h - want_h) <= 1
    results.append((f"rasterises to {want_w} x {want_h} px @ {PRINT_DPI} DPI",
                    ok, f"pdftoppm -r {PRINT_DPI} gives {px_w} x {px_h} px"))

    text = _norm(pdf_text(path))

    # --- Gate 4: official-card provenance ---------------------------------
    revision = [m for m in (MARKER_REVISION, MARKER_OMB) if _norm(m) in text]
    agency = _norm(MARKER_AGENCY) in text
    found = revision + ([MARKER_AGENCY] if agency else [])
    results.append(("official FBI card markers present",
                    bool(revision) and agency,
                    "found: " + "; ".join(found) if found else
                    f"none of {MARKER_REVISION!r} / {MARKER_OMB!r} / "
                    f"{MARKER_AGENCY!r} found - this is not the official card"))

    # --- Gate 5: official field labels ------------------------------------
    if check_fields:
        missing = [t for t in REQUIRED_TEXT if _norm(t) not in text]
        results.append(("official FD-258 field labels present", not missing,
                        "all %d labels found" % len(REQUIRED_TEXT) if not missing
                        else f"missing: {', '.join(missing)}"))

    return all(ok for _, ok, _ in results), results


def print_report(path: str, results: list[tuple[str, bool, str]]) -> None:
    print(f"QA gate: {path}")
    print("-" * 72)
    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        print(f"       {detail}")
    print("-" * 72)
    print("RESULT: " + ("PASS" if all(ok for _, ok, _ in results) else "FAIL"))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def safe_name_part(value: str) -> str:
    """Uppercase, strip anything that does not belong in a filename."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", (value or "").strip()).strip("-")
    return cleaned.upper() or "UNKNOWN"


def default_filename(lastname: str | None, firstname: str | None) -> str:
    """FD-258_<LASTNAME>_<FIRSTNAME>.pdf"""
    return "FD-258_%s_%s.pdf" % (safe_name_part(lastname or "BLANK"),
                                 safe_name_part(firstname or "CARD"))


def collect_data(args: argparse.Namespace) -> dict:
    """Pull the (optional) pre-fill values off the parsed CLI args."""
    return {k: v for k in DATA_KEYS if (v := getattr(args, k, None))}


def cmd_generate(args: argparse.Namespace) -> int:
    data = collect_data(args)
    out = args.out or default_filename(args.lastname, args.firstname)
    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)
        out = os.path.join(args.outdir, os.path.basename(out))
    parent = os.path.dirname(os.path.abspath(out))
    os.makedirs(parent, exist_ok=True)

    source = args.source or official_card_path()
    if args.raster:
        build_raster_pdf(out, data, letter=args.letter, dpi=args.dpi,
                         source=source)
        mode = f"official card, re-rendered at {args.dpi} DPI"
    else:
        build_official_pdf(out, data, letter=args.letter, source=source)
        mode = "official card as published" + (
            " (mounted on US Letter)" if args.letter else "")

    size = "612 x 792 pt (US Letter)" if args.letter else "576 x 576 pt (8\" x 8\")"
    print(f"Wrote {out}")
    print(f"  source    : {source}")
    print(f"  mode      : {mode}")
    print(f"  page size : {size}, {OFFICIAL_PAGES} pages (front + back)")
    filled = sorted(resolve_data(data))
    print(f"  fields    : {'overlay pre-fill: ' + ', '.join(filled) if filled else 'blank (manual ink workflow)'}")
    print("  print at 100% / \"Actual size\" - do not fit-to-page.")

    if args.verify:
        ok, results = verify_pdf(out, letter=args.letter)
        print()
        print_report(out, results)
        return 0 if ok else 1
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    ok, results = verify_pdf(args.file, letter=args.letter,
                             check_fields=not args.no_fields)
    print_report(args.file, results)
    return 0 if ok else 1


def cmd_fetch(args: argparse.Namespace) -> int:
    """Refresh the bundled copy of the official card from fbi.gov."""
    dest = download_official_card(args.dest)
    print(f"Downloaded {OFFICIAL_URL}\n  -> {dest} ({os.path.getsize(dest)} bytes)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fd258_card.py",
        description="Generate and QA-verify print-ready copies of the OFFICIAL "
                    "FBI FD-258 fingerprint card (8\" x 8\", from fbi.gov).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
               "  fd258_card.py generate --out FD-258_GROS_MARCELO.pdf\n"
               "  fd258_card.py generate --lastname Gros --firstname Marcelo\n"
               "  fd258_card.py generate --letter --out card_letter.pdf\n"
               "  fd258_card.py verify --file FD-258_GROS_MARCELO.pdf\n"
               "  fd258_card.py fetch     # refresh official/ from fbi.gov\n")
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate",
                       help="write the official card (blank, or pre-filled)")
    g.add_argument("--out", help="output path (default FD-258_<LAST>_<FIRST>.pdf)")
    g.add_argument("--outdir", help="directory to write the PDF into")
    g.add_argument("--letter", action="store_true",
                   help="mount each official page at 100%% on US Letter "
                        "with trim marks")
    g.add_argument("--raster", action="store_true",
                   help="re-render the official pages at %d DPI and embed them"
                        % PRINT_DPI)
    g.add_argument("--dpi", type=int, default=PRINT_DPI,
                   help="raster resolution for --raster (default/minimum %d)" % PRINT_DPI)
    g.add_argument("--source", help="official FD-258 PDF to use "
                                    "(default: official/ cache, else fbi.gov)")
    g.add_argument("--verify", action="store_true",
                   help="run the QA gate on the file just written")

    fill = g.add_argument_group(
        "optional pre-fill overlay (card is blank by default; signature boxes "
        "are never filled)")
    fill.add_argument("--lastname")
    fill.add_argument("--firstname")
    fill.add_argument("--middlename")
    fill.add_argument("--aliases")
    fill.add_argument("--residence")
    fill.add_argument("--citizenship")
    fill.add_argument("--dob", help="date of birth, Month Day Year")
    fill.add_argument("--sex")
    fill.add_argument("--race")
    fill.add_argument("--height")
    fill.add_argument("--weight")
    fill.add_argument("--eyes")
    fill.add_argument("--hair")
    fill.add_argument("--pob", help="place of birth")
    fill.add_argument("--ssn", help="social security number")
    fill.add_argument("--employer", help="employer and address")
    fill.add_argument("--contributor", help="alias for --employer")
    fill.add_argument("--reason", help="reason fingerprinted")
    fill.add_argument("--ori", help="originating agency identifier")
    fill.add_argument("--oca", help="your number / OCA")
    fill.add_argument("--date-fingerprinted", dest="date_fingerprinted")
    fill.add_argument("--date-signed", dest="date_signed",
                      help="alias for --date-fingerprinted (one DATE box)")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("verify", help="run the QA gate against a PDF")
    v.add_argument("--file", required=True, help="PDF to check")
    v.add_argument("--letter", action="store_true",
                   help="expect the US Letter layout (612x792 pt)")
    v.add_argument("--no-fields", action="store_true",
                   help="skip the FD-258 field-label text check")
    v.set_defaults(func=cmd_verify)

    f = sub.add_parser("fetch", help="download the official FD-258 from fbi.gov")
    f.add_argument("--dest", default=OFFICIAL_CACHE,
                   help="where to store it (default %(default)s)")
    f.set_defaults(func=cmd_fetch)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
