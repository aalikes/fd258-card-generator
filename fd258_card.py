#!/usr/bin/env python3
"""
fd258_card.py — print-ready FBI FD-258 fingerprint card generator.

Produces a true-size 8" x 8" (576 x 576 pt) FD-258 fingerprint card as a
single-page PDF, ready for manual ink fingerprinting and mailing to:

    FBI CJIS Division
    ATTN: ELECTRONIC SUMMARY REQUEST
    1000 Custer Hollow Road
    Clarksburg, WV 26306

(Always mail the card together with a copy of the FBI EDO order confirmation
email.)

Design notes
------------
* The card is drawn as **vector** art with reportlab's canvas API, so it stays
  crisp at any output resolution.  A 576x576 pt page rasterises to exactly
  2400 x 2400 px at 300 DPI (576 / 72 * 300 = 2400), which is the canonical
  print-ready build.  The rejected "576x576 @ 72 ppi" build is a blurry raster
  downsample and this tool never produces it.
* ``--raster`` re-renders that vector page through poppler at 300 DPI and
  embeds the resulting 2400 x 2400 px image in a 576x576 pt page.  The embedded
  raster is then *literally* 300 DPI (``pdfimages -list`` reports 300/300),
  which is what the sample card ships as.
* ``--letter`` centres the same 8x8 card, at 100% scale, on US Letter
  (612 x 792 pt) with trim marks, for printing at a library/office printer and
  trimming down to 8x8.

Dependencies: reportlab only (poppler-utils for ``verify`` and ``--raster``).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

from reportlab.lib.colors import Color, black, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as rl_canvas

# --------------------------------------------------------------------------- #
# Page / card geometry  (all values in PostScript points, 72 pt == 1 inch)
# --------------------------------------------------------------------------- #

PT_PER_INCH = 72.0

CARD_SIZE = 576.0                     # 8.00 in  -> HARD REQUIREMENT #1
LETTER_W, LETTER_H = 612.0, 792.0     # US Letter -> HARD REQUIREMENT #4

PRINT_DPI = 300                       # HARD REQUIREMENT #2
CARD_PX_AT_300 = int(round(CARD_SIZE / PT_PER_INCH * PRINT_DPI))   # == 2400

MARGIN = 18.0                         # 0.25 in quiet zone inside the card
CONTENT = CARD_SIZE - 2 * MARGIN      # == 540 pt of drawable width/height

# Vertical stack of the card, top to bottom.  The sum of every band plus the
# gaps between them must be exactly CONTENT; this is asserted at import time.
H_HEADER = 54.0        # FBI/DOJ masthead + ORI / OCA / DATE + LEAVE BLANK
H_INSTR = 11.0         # "TYPE OR PRINT ALL INFORMATION IN BLACK" strip
H_DATA = 134.0         # personal-data field grid
H_ROLLED = 118.0       # one row of five rolled impressions (x2)
H_PLAIN = 90.0         # simultaneous four-finger + thumb impressions
GAP = 3.0              # gap between bands

# Line weights.  Deliberately chunky: thin hairlines disappear on cheap laser
# printers and the boxes have to stay legible under ink.
LW_FRAME = 1.4         # card outer frame
LW_BOX = 1.0           # field / impression boxes
LW_RULE = 0.6          # internal dividers (label strips, etc.)

# Typography
F_LABEL = "Helvetica"          # field captions
F_CODE = "Helvetica-Bold"      # NCIC field codes (NAM, DOB, ...)
F_VALUE = "Helvetica"          # operator-supplied values
F_HEAD = "Helvetica-Bold"
SZ_LABEL = 5.0
SZ_CODE = 5.0
SZ_VALUE = 9.0

CAP_PAD = 2.0          # inset of a caption from its box corner
GREY = Color(0.45, 0.45, 0.45)

# --------------------------------------------------------------------------- #
# Field grid definition
# --------------------------------------------------------------------------- #
# Each data row is (height, [(caption, ncic_code, data_key, width), ...]).
# Widths in a row must sum to CONTENT (asserted below).

DATA_ROWS = [
    (22.0, [
        ("LAST NAME", "NAM", "lastname", 200.0),
        ("FIRST NAME", None, "firstname", 170.0),
        ("MIDDLE NAME", None, "middlename", 170.0),
    ]),
    (22.0, [
        ("SIGNATURE OF PERSON FINGERPRINTED", None, None, 330.0),
        ("ALIASES", "AKA", "aliases", 210.0),
    ]),
    (22.0, [
        ("RESIDENCE OF PERSON FINGERPRINTED", "RES", "residence", 380.0),
        ("COUNTRY OF CITIZENSHIP", "CTZ", "citizenship", 160.0),
    ]),
    (20.0, [
        ("DATE OF BIRTH  (MM DD YYYY)", "DOB", "dob", 96.0),
        ("SEX", None, "sex", 44.0),
        ("RACE", None, "race", 50.0),
        ("HGT", None, "height", 46.0),
        ("WGT", None, "weight", 46.0),
        ("EYES", None, "eyes", 50.0),
        ("HAIR", None, "hair", 50.0),
        ("PLACE OF BIRTH", "POB", "pob", 158.0),
    ]),
    (22.0, [
        ("SIGNATURE OF OFFICIAL TAKING FINGERPRINTS", None, None, 300.0),
        ("DATE SIGNED", None, "date_signed", 110.0),
        ("SOCIAL SECURITY NO.", "SOC", "ssn", 130.0),
    ]),
    (26.0, [
        ("CONTRIBUTOR'S NAME AND ADDRESS", None, "contributor", 300.0),
        ("REASON FINGERPRINTED", None, "reason", 240.0),
    ]),
]

# Rolled impressions: 5 across, 2 rows.  Numbering follows the FD-258.
ROLLED_RIGHT = ["1. R. THUMB", "2. R. INDEX", "3. R. MIDDLE",
                "4. R. RING", "5. R. LITTLE"]
ROLLED_LEFT = ["6. L. THUMB", "7. L. INDEX", "8. L. MIDDLE",
               "9. L. RING", "10. L. LITTLE"]

# Bottom band: plain (simultaneous) impressions.
PLAIN_BLOCKS = [
    ("LEFT FOUR FINGERS TAKEN SIMULTANEOUSLY", 170.0),
    ("L. THUMB", 100.0),
    ("R. THUMB", 100.0),
    ("RIGHT FOUR FINGERS TAKEN SIMULTANEOUSLY", 170.0),
]

MASTHEAD = [
    ("FEDERAL BUREAU OF INVESTIGATION", F_HEAD, 9.0),
    ("UNITED STATES DEPARTMENT OF JUSTICE", F_LABEL, 7.0),
    ("WASHINGTON, D.C. 20537", F_LABEL, 6.0),
    ("FINGERPRINT CARD", F_HEAD, 8.5),
]

INSTRUCTION = ("TYPE OR PRINT ALL INFORMATION IN BLACK  •  "
               "SIGNATURE OF PERSON FINGERPRINTED MUST BE MADE IN THE "
               "PRESENCE OF THE OFFICIAL TAKING THE FINGERPRINTS")

CJIS_ADDRESS = ("FBI CJIS Division, ATTN: ELECTRONIC SUMMARY REQUEST, "
                "1000 Custer Hollow Road, Clarksburg, WV 26306")

# Every data key the CLI can pre-fill.
DATA_KEYS = [
    "lastname", "firstname", "middlename", "aliases", "residence",
    "citizenship", "dob", "sex", "race", "height", "weight", "eyes", "hair",
    "pob", "date_signed", "ssn", "contributor", "reason", "ori", "oca",
    "date_fingerprinted",
]


def _validate_geometry() -> None:
    """Fail loudly at import time if the layout no longer adds up to 8x8."""
    bands = [H_HEADER, H_INSTR, H_DATA, H_ROLLED, H_ROLLED, H_PLAIN]
    total = sum(bands) + GAP * (len(bands) - 1)
    assert abs(total - CONTENT) < 1e-6, f"card bands sum to {total}, want {CONTENT}"
    assert abs(sum(h for h, _ in DATA_ROWS) - H_DATA) < 1e-6, "data rows misfit"
    for _, cells in DATA_ROWS:
        w = sum(c[3] for c in cells)
        assert abs(w - CONTENT) < 1e-6, f"data row width {w}, want {CONTENT}"
    assert abs(sum(w for _, w in PLAIN_BLOCKS) - CONTENT) < 1e-6, "plain row misfit"


_validate_geometry()


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
                size: float, max_w: float, align: str = "left") -> None:
    """Draw `text` at baseline `y`, auto-shrinking so it never overflows."""
    if not text:
        return
    size = fit_size(text, font, size, max_w)
    c.setFont(font, size)
    if align == "center":
        c.drawCentredString(x, y, text)
    elif align == "right":
        c.drawRightString(x, y, text)
    else:
        c.drawString(x, y, text)


def box(c: rl_canvas.Canvas, x: float, top: float, w: float, h: float,
        lw: float = LW_BOX) -> None:
    """Stroke a rectangle given its *top* edge (top-down layout convenience)."""
    c.setLineWidth(lw)
    c.setStrokeColor(black)
    c.rect(x, top - h, w, h, stroke=1, fill=0)


def field(c: rl_canvas.Canvas, x: float, top: float, w: float, h: float,
          caption: str, code: str | None = None, value: str | None = None,
          value_size: float = SZ_VALUE) -> None:
    """
    Draw one form field: a box, a small caption in the top-left corner, an
    optional NCIC code in the top-right corner, and an optional filled value
    sitting on the writing line near the bottom of the box.
    """
    box(c, x, top, w, h)

    c.setFillColor(black)
    cap_w = w - 2 * CAP_PAD - (14.0 if code else 0.0)
    draw_fitted(c, x + CAP_PAD, top - CAP_PAD - SZ_LABEL, caption,
                F_LABEL, SZ_LABEL, cap_w)
    if code:
        c.setFillColor(GREY)
        draw_fitted(c, x + w - CAP_PAD, top - CAP_PAD - SZ_CODE, code,
                    F_CODE, SZ_CODE, 14.0, align="right")
        c.setFillColor(black)

    if value:
        draw_fitted(c, x + CAP_PAD + 1.0, top - h + 4.0, str(value),
                    F_VALUE, value_size, w - 2 * CAP_PAD - 2.0)


def impression_block(c: rl_canvas.Canvas, x: float, top: float, w: float,
                     h: float, label: str) -> None:
    """
    One fingerprint impression box: a heavier border, a thin label strip across
    the top, and a large clean white area for the inked impression.
    """
    box(c, x, top, w, h, lw=LW_BOX)
    strip_h = 11.0
    c.setLineWidth(LW_RULE)
    c.setStrokeColor(black)
    c.line(x, top - strip_h, x + w, top - strip_h)
    c.setFillColor(black)
    draw_fitted(c, x + w / 2.0, top - strip_h + 3.4, label,
                F_CODE, 6.0, w - 4.0, align="center")


def band_label(c: rl_canvas.Canvas, x: float, top: float, w: float, h: float,
               left: str, right: str) -> None:
    """Row caption strip drawn above a row of impression blocks."""
    c.setFillColor(black)
    draw_fitted(c, x + 2.0, top - h + 2.0, left, F_HEAD, 7.0, w * 0.45)
    c.setFillColor(GREY)
    draw_fitted(c, x + w - 2.0, top - h + 2.0, right, F_LABEL, 5.5,
                w * 0.5, align="right")
    c.setFillColor(black)


# --------------------------------------------------------------------------- #
# Card drawing
# --------------------------------------------------------------------------- #

def draw_card(c: rl_canvas.Canvas, ox: float, oy: float,
              data: dict | None = None) -> None:
    """
    Draw a complete FD-258 card whose lower-left corner is at (ox, oy).

    Everything is vector: lines and text only, no rasters, so the result is
    resolution independent and rasterises cleanly at 300 DPI or higher.
    """
    data = data or {}
    left = ox + MARGIN
    right = left + CONTENT
    top = oy + CARD_SIZE - MARGIN     # top edge of the content area

    c.setFillColor(black)
    c.setStrokeColor(black)

    # ---- card frame -------------------------------------------------------
    c.setLineWidth(LW_FRAME)
    c.rect(left, oy + MARGIN, CONTENT, CONTENT, stroke=1, fill=0)

    y = top

    # ---- header band ------------------------------------------------------
    _draw_header(c, left, y, data)
    y -= H_HEADER + GAP

    # ---- instruction strip ------------------------------------------------
    box(c, left, y, CONTENT, H_INSTR, lw=LW_RULE)
    draw_fitted(c, left + CONTENT / 2.0, y - H_INSTR + 3.6, INSTRUCTION,
                F_LABEL, 5.6, CONTENT - 8.0, align="center")
    y -= H_INSTR + GAP

    # ---- personal data grid ----------------------------------------------
    for row_h, cells in DATA_ROWS:
        x = left
        for caption, code, key, w in cells:
            field(c, x, y, w, row_h, caption, code,
                  data.get(key) if key else None)
            x += w
        y -= row_h
    y -= GAP

    # ---- rolled impressions: right hand, then left hand -------------------
    for labels, hand in ((ROLLED_RIGHT, "RIGHT HAND"), (ROLLED_LEFT, "LEFT HAND")):
        band_h = 10.0
        band_label(c, left, y, CONTENT, band_h, hand,
                   "ROLLED IMPRESSIONS — ROLL EACH FINGER NAIL TO NAIL")
        y -= band_h
        blk_h = H_ROLLED - band_h
        blk_w = CONTENT / 5.0
        for i, label in enumerate(labels):
            impression_block(c, left + i * blk_w, y, blk_w, blk_h, label)
        y -= blk_h + GAP

    # ---- plain (simultaneous) impressions --------------------------------
    band_h = 10.0
    band_label(c, left, y, CONTENT, band_h,
               "PLAIN IMPRESSIONS — TAKEN SIMULTANEOUSLY",
               "PRESS FINGERS FLAT — DO NOT ROLL")
    y -= band_h
    blk_h = H_PLAIN - band_h
    x = left
    for label, w in PLAIN_BLOCKS:
        impression_block(c, x, y, w, blk_h, label)
        x += w
    y -= blk_h

    # Bottom of the stack must land exactly on the card's bottom margin.
    assert abs(y - (oy + MARGIN)) < 1e-6, f"layout drift: {y - (oy + MARGIN)}"

    # Fine print, tucked inside the bottom impression band's baseline area.
    c.setFillColor(GREY)
    draw_fitted(c, right, oy + MARGIN - 7.0, "FD-258 (8\" × 8\")",
                F_LABEL, 4.5, 120.0, align="right")
    c.setFillColor(black)


def _draw_header(c: rl_canvas.Canvas, left: float, top: float,
                 data: dict) -> None:
    """
    Header band: administrative boxes on the left (ORI / OCA / DATE), the
    FBI masthead in the middle, and the FBI-use "LEAVE BLANK" box at right.
    """
    col_l_w = 190.0
    col_r_w = 168.0
    col_c_x = left + col_l_w
    col_c_w = CONTENT - col_l_w - col_r_w

    # Left: three stacked administrative fields.
    admin = [
        ("ORIGINATING AGENCY IDENTIFIER", "ORI", "ori"),
        ("YOUR NO.", "OCA", "oca"),
        ("DATE FINGERPRINTED  (MM DD YYYY)", None, "date_fingerprinted"),
    ]
    row_h = H_HEADER / len(admin)
    y = top
    for caption, code, key in admin:
        field(c, left, y, col_l_w, row_h, caption, code, data.get(key),
              value_size=8.0)
        y -= row_h

    # Centre: masthead.  Lines are vertically distributed inside the band.
    line_gap = (H_HEADER - sum(s for _, _, s in MASTHEAD)) / (len(MASTHEAD) + 1)
    ty = top - line_gap
    cx = col_c_x + col_c_w / 2.0
    for text, font, size in MASTHEAD:
        ty -= size
        draw_fitted(c, cx, ty, text, font, size, col_c_w - 6.0, align="center")
        ty -= line_gap

    # Right: FBI-use block.
    box(c, left + CONTENT - col_r_w, top, col_r_w, H_HEADER)
    c.setFillColor(GREY)
    draw_fitted(c, left + CONTENT - col_r_w / 2.0, top - H_HEADER / 2.0 - 3.0,
                "LEAVE BLANK", F_CODE, 8.0, col_r_w - 8.0, align="center")
    c.setFillColor(black)


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


def _letter_notes(c: rl_canvas.Canvas, ox: float, oy: float) -> None:
    """Printing instructions above the card, mailing note below it."""
    cx = LETTER_W / 2.0
    c.setFillColor(black)
    draw_fitted(c, cx, oy + CARD_SIZE + 62.0,
                "FBI FD-258 FINGERPRINT CARD — PRINT AT 100% (\"ACTUAL "
                "SIZE\"), THEN TRIM ON THE MARKS TO 8\" × 8\"",
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

def _new_canvas(path: str, w: float, h: float, title: str) -> rl_canvas.Canvas:
    c = rl_canvas.Canvas(path, pagesize=(w, h))
    c.setTitle(title)
    c.setAuthor("fd258_card.py")
    c.setSubject("FBI FD-258 fingerprint card, 8x8 in, print at 100%%")
    c.setCreator("fd258_card.py (reportlab)")
    return c


def build_vector_pdf(path: str, data: dict | None = None,
                     letter: bool = False) -> str:
    """Write the vector card (8x8) or the letter-mounted card to `path`."""
    title = "FD-258 Fingerprint Card" + (" (US Letter)" if letter else "")
    if letter:
        c = _new_canvas(path, LETTER_W, LETTER_H, title)
        ox = (LETTER_W - CARD_SIZE) / 2.0          # 18 pt
        oy = (LETTER_H - CARD_SIZE) / 2.0          # 108 pt  -> 100% scale
        _trim_marks(c, ox, oy)
        _letter_notes(c, ox, oy)
        draw_card(c, ox, oy, data)
    else:
        c = _new_canvas(path, CARD_SIZE, CARD_SIZE, title)
        draw_card(c, 0.0, 0.0, data)
    c.showPage()
    c.save()
    return path


class _InvisibleTextCanvas:
    """
    Canvas proxy that draws *only* text, and draws it invisibly (PDF text
    render mode 3).  Used to lay an extractable text layer over the raster
    build so the card stays searchable/accessible and so the QA gate's field
    check works on raster PDFs exactly as it does on vector ones.
    """

    def __init__(self, canvas: rl_canvas.Canvas):
        self._c = canvas

    def __getattr__(self, name):                    # forward everything else
        return getattr(self._c, name)

    # geometry is already in the bitmap - drop it
    def rect(self, *a, **k): pass
    def line(self, *a, **k): pass
    def setLineWidth(self, *a, **k): pass
    def setStrokeColor(self, *a, **k): pass

    def drawString(self, x, y, text, **k):
        self._c.drawString(x, y, text, mode=3, **k)

    def drawCentredString(self, x, y, text, **k):
        self._c.drawCentredString(x, y, text, mode=3, **k)

    def drawRightString(self, x, y, text, **k):
        self._c.drawRightString(x, y, text, mode=3, **k)


def build_raster_pdf(path: str, data: dict | None = None,
                     letter: bool = False, dpi: int = PRINT_DPI) -> str:
    """
    Render the vector card through poppler at `dpi` and embed the resulting
    bitmap at 1:1 page scale, so the PDF carries a *literal* `dpi` raster
    (``pdfimages -list`` reports it).  `dpi` below 300 is refused: a 72-DPI
    downsample is the exact regression the QA gate exists to catch.
    """
    if dpi < PRINT_DPI:
        raise ValueError(f"--dpi must be >= {PRINT_DPI} (got {dpi}); "
                         "anything lower fails the QA gate")
    require_tool("pdftoppm")
    page_w, page_h = (LETTER_W, LETTER_H) if letter else (CARD_SIZE, CARD_SIZE)

    with tempfile.TemporaryDirectory() as tmp:
        vec = os.path.join(tmp, "vector.pdf")
        build_vector_pdf(vec, data, letter=letter)
        stem = os.path.join(tmp, "page")
        run(["pdftoppm", "-r", str(dpi), "-png", "-gray", "-aa", "yes",
             "-aaVector", "yes", "-f", "1", "-l", "1", vec, stem])
        pngs = sorted(f for f in os.listdir(tmp) if f.endswith(".png"))
        if not pngs:
            raise RuntimeError("pdftoppm produced no output")
        png = os.path.join(tmp, pngs[0])

        c = _new_canvas(path, page_w, page_h,
                        f"FD-258 Fingerprint Card ({dpi} DPI)")
        # Draw the bitmap across the whole page: N px over (page/72) in
        # => exactly `dpi` DPI in the output PDF.
        c.drawImage(png, 0, 0, width=page_w, height=page_h)
        # Invisible text layer, positioned identically to the vector build.
        ox = (page_w - CARD_SIZE) / 2.0
        oy = (page_h - CARD_SIZE) / 2.0
        draw_card(_InvisibleTextCanvas(c), ox, oy, data)
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


REQUIRED_TEXT = [
    "FEDERAL BUREAU OF INVESTIGATION",
    "UNITED STATES DEPARTMENT OF JUSTICE",
    "FINGERPRINT CARD",
    "ORI", "OCA",
    "LAST NAME", "FIRST NAME", "MIDDLE NAME", "ALIASES", "RESIDENCE",
    "DATE OF BIRTH", "SEX", "RACE", "HGT", "WGT", "EYES", "HAIR",
    "PLACE OF BIRTH",
    "SIGNATURE OF PERSON FINGERPRINTED",
    "CONTRIBUTOR'S NAME AND ADDRESS",
    "REASON FINGERPRINTED",
    "SIGNATURE OF OFFICIAL TAKING FINGERPRINTS",
    "RIGHT HAND", "LEFT HAND",
    "R. THUMB", "R. INDEX", "R. MIDDLE", "R. RING", "R. LITTLE",
    "L. THUMB", "L. INDEX", "L. MIDDLE", "L. RING", "L. LITTLE",
    "LEFT FOUR FINGERS TAKEN SIMULTANEOUSLY",
    "RIGHT FOUR FINGERS TAKEN SIMULTANEOUSLY",
]


def pdf_text(path: str) -> str:
    require_tool("pdftotext")
    return run(["pdftotext", "-layout", path, "-"])


def verify_pdf(path: str, letter: bool = False,
               check_fields: bool = True) -> tuple[bool, list[tuple[str, bool, str]]]:
    """
    Run the QA gate.  Returns (all_passed, [(check_name, passed, detail), ...]).

    Gate 1  page size is exactly 576x576 pt (or 612x792 pt in --letter mode)
    Gate 2  300 DPI print readiness:
              * if the PDF embeds rasters, every one must be >= 300 DPI
                (this is what rejects the blurry 72-ppi build), and
              * the page must rasterise to the expected 300-DPI pixel size
    Gate 3  the required FD-258 field labels are present (optional)
    """
    results: list[tuple[str, bool, str]] = []
    exp_w, exp_h = (LETTER_W, LETTER_H) if letter else (CARD_SIZE, CARD_SIZE)
    label = "letter 612x792" if letter else "card 576x576"

    if not os.path.isfile(path):
        return False, [("file exists", False, f"{path} not found")]

    # --- Gate 1: page size ------------------------------------------------
    w, h, pages = pdf_page_size(path)
    ok = abs(w - exp_w) < 0.5 and abs(h - exp_h) < 0.5
    results.append((f"page size == {int(exp_w)} x {int(exp_h)} pts ({label})",
                    ok, f"pdfinfo reports {w:g} x {h:g} pts, {pages} page(s)"))
    results.append(("single page", pages == 1, f"{pages} page(s)"))

    # --- Gate 2a: embedded raster resolution ------------------------------
    images = embedded_image_dpi(path)
    if images:
        worst = min(min(x, y) for _, _, x, y in images)
        detail = "; ".join(f"{iw}x{ih}px @ {xp}x{yp} dpi"
                           for iw, ih, xp, yp in images)
        results.append((f"embedded raster DPI >= {PRINT_DPI}",
                        worst >= PRINT_DPI, detail))
    else:
        results.append((f"embedded raster DPI >= {PRINT_DPI}", True,
                        "no embedded rasters - pure vector art "
                        "(resolution independent)"))

    # --- Gate 2b: 300-DPI rasterisation ----------------------------------
    px_w, px_h = raster_dimensions(path, PRINT_DPI)
    want_w = int(round(exp_w / PT_PER_INCH * PRINT_DPI))
    want_h = int(round(exp_h / PT_PER_INCH * PRINT_DPI))
    ok = abs(px_w - want_w) <= 1 and abs(px_h - want_h) <= 1
    results.append((f"rasterises to {want_w} x {want_h} px @ {PRINT_DPI} DPI",
                    ok, f"pdftoppm -r {PRINT_DPI} gives {px_w} x {px_h} px"))

    # --- Gate 3: required fields -----------------------------------------
    if check_fields:
        text = " ".join(pdf_text(path).split()).upper()
        missing = [t for t in REQUIRED_TEXT
                   if " ".join(t.split()).upper() not in text]
        results.append(("required FD-258 fields present", not missing,
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
    """FD-258_<LASTNAME>_<FIRSTNAME>.pdf, per hard requirement #3."""
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

    if args.raster:
        build_raster_pdf(out, data, letter=args.letter, dpi=args.dpi)
        mode = f"raster ({args.dpi} DPI embedded)"
    else:
        build_vector_pdf(out, data, letter=args.letter)
        mode = "vector"

    size = "612 x 792 pt (US Letter)" if args.letter else "576 x 576 pt (8\" x 8\")"
    print(f"Wrote {out}")
    print(f"  mode      : {mode}")
    print(f"  page size : {size}")
    print(f"  fields    : {'pre-filled: ' + ', '.join(sorted(data)) if data else 'blank'}")
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fd258_card.py",
        description="Generate and QA-verify print-ready FBI FD-258 "
                    "fingerprint cards (8\" x 8\", 300 DPI).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
               "  fd258_card.py generate --out FD-258_GROS_MARCELO.pdf\n"
               "  fd258_card.py generate --lastname Gros --firstname Marcelo\n"
               "  fd258_card.py generate --letter --out card_letter.pdf\n"
               "  fd258_card.py verify --file FD-258_GROS_MARCELO.pdf\n")
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="write a blank or pre-filled card PDF")
    g.add_argument("--out", help="output path (default FD-258_<LAST>_<FIRST>.pdf)")
    g.add_argument("--outdir", help="directory to write the PDF into")
    g.add_argument("--letter", action="store_true",
                   help="mount the 8x8 card at 100%% on US Letter with trim marks")
    g.add_argument("--raster", action="store_true",
                   help="embed a %d DPI rendering instead of vector art" % PRINT_DPI)
    g.add_argument("--dpi", type=int, default=PRINT_DPI,
                   help="raster resolution for --raster (default/minimum %d)" % PRINT_DPI)
    g.add_argument("--verify", action="store_true",
                   help="run the QA gate on the file just written")

    fill = g.add_argument_group("optional pre-fill (card is blank by default)")
    fill.add_argument("--lastname")
    fill.add_argument("--firstname")
    fill.add_argument("--middlename")
    fill.add_argument("--aliases")
    fill.add_argument("--residence")
    fill.add_argument("--citizenship")
    fill.add_argument("--dob", help="date of birth, MM DD YYYY")
    fill.add_argument("--sex")
    fill.add_argument("--race")
    fill.add_argument("--height")
    fill.add_argument("--weight")
    fill.add_argument("--eyes")
    fill.add_argument("--hair")
    fill.add_argument("--pob", help="place of birth")
    fill.add_argument("--ssn", help="social security number")
    fill.add_argument("--date-signed", dest="date_signed")
    fill.add_argument("--contributor", help="contributor's name and address")
    fill.add_argument("--reason", help="reason fingerprinted")
    fill.add_argument("--ori", help="originating agency identifier")
    fill.add_argument("--oca", help="your number / OCA")
    fill.add_argument("--date-fingerprinted", dest="date_fingerprinted")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("verify", help="run the QA gate against a PDF")
    v.add_argument("--file", required=True, help="PDF to check")
    v.add_argument("--letter", action="store_true",
                   help="expect the US Letter layout (612x792 pt)")
    v.add_argument("--no-fields", action="store_true",
                   help="skip the FD-258 field-label text check")
    v.set_defaults(func=cmd_verify)
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
