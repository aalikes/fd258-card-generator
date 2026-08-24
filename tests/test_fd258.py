#!/usr/bin/env python3
"""
QA gate tests for fd258_card.py.

Run with the hermes venv interpreter (pypdf + reportlab live there):

    /usr/local/lib/hermes-agent/venv/bin/python -m unittest discover -s tests -v
    # or:  make test

The requirements asserted here:
  0. the output comes from the OFFICIAL FBI FD-258 (fbi.gov), not a drawing --
     proven by the revision / OMB / agency text markers
  1. card page size is exactly 576 x 576 pt (8" x 8"), both official pages
  2. the card is print-ready at 300 DPI -- it rasterises to 2400 x 2400 px and
     any embedded raster is >= 300 DPI (a 72-DPI build must FAIL the gate)
  3. output is a single PDF named FD-258_<LASTNAME>_<FIRSTNAME>.pdf
plus the --letter mode (612 x 792 pt) and the official field inventory.

These tests never hit the network: they run against the bundled
official/fd-258-official-fillable.pdf cache.
"""

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fd258_card as fd  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "fd258_card.py")
SAMPLE = os.path.join(REPO, "samples", "FD-258_GROS_MARCELO.pdf")
OFFICIAL = fd.OFFICIAL_CACHE


def cli(*args):
    """Run the tool's CLI; returns (returncode, stdout+stderr)."""
    proc = subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def path(self, name):
        return os.path.join(self.tmp, name)


class TestOfficialSource(unittest.TestCase):
    """Requirement 0: the card is the FBI's own FD-258."""

    def test_official_pdf_is_bundled(self):
        self.assertTrue(os.path.isfile(OFFICIAL),
                        "official/fd-258-official-fillable.pdf is missing; "
                        "run `make fetch`")
        self.assertGreaterEqual(os.path.getsize(OFFICIAL), fd.OFFICIAL_MIN_BYTES)

    def test_official_pdf_is_the_true_size_two_page_card(self):
        w, h, pages = fd.pdf_page_size(OFFICIAL)
        self.assertEqual((w, h), (576.0, 576.0))
        self.assertEqual(pages, fd.OFFICIAL_PAGES)

    def test_official_pdf_carries_the_fbi_markers(self):
        text = " ".join(fd.pdf_text(OFFICIAL).split()).upper()
        self.assertIn(fd.MARKER_REVISION.upper(), text)
        self.assertIn(fd.MARKER_OMB.upper(), text)
        self.assertIn(fd.MARKER_AGENCY.upper(), text)

    def test_official_url_points_at_fbi_gov(self):
        self.assertTrue(fd.OFFICIAL_URL.startswith("https://www.fbi.gov/"),
                        fd.OFFICIAL_URL)

    def test_cache_is_used_without_downloading(self):
        self.assertEqual(fd.official_card_path(allow_download=False), OFFICIAL)

    def test_missing_cache_without_download_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                fd.official_card_path(os.path.join(tmp, "nope.pdf"),
                                      allow_download=False)

    def test_generated_card_is_byte_identical_content_to_the_official_pages(self):
        """A blank card must carry the official text, verbatim."""
        with tempfile.TemporaryDirectory() as tmp:
            out = fd.build_official_pdf(os.path.join(tmp, "blank.pdf"),
                                        source=OFFICIAL)
            self.assertEqual(" ".join(fd.pdf_text(out).split()),
                             " ".join(fd.pdf_text(OFFICIAL).split()))


class TestHardRequirement1PageSize(TempDirCase):
    """576 x 576 pt, exactly, both official pages."""

    def test_card_is_576_by_576(self):
        pdf = fd.build_official_pdf(self.path("card.pdf"), source=OFFICIAL)
        w, h, pages = fd.pdf_page_size(pdf)
        self.assertEqual((w, h), (576.0, 576.0))
        self.assertEqual(pages, fd.OFFICIAL_PAGES)

    def test_letter_mode_is_612_by_792(self):
        pdf = fd.build_official_pdf(self.path("letter.pdf"), letter=True,
                                    source=OFFICIAL)
        w, h, pages = fd.pdf_page_size(pdf)
        self.assertEqual((w, h), (612.0, 792.0))
        self.assertEqual(pages, fd.OFFICIAL_PAGES)

    def test_letter_embeds_card_at_100_percent(self):
        """The card must sit unscaled and centred on the letter sheet."""
        self.assertAlmostEqual(fd.LETTER_OX, 18.0)
        self.assertAlmostEqual(fd.LETTER_OY, 108.0)
        letter = fd.build_official_pdf(self.path("letter.pdf"), letter=True,
                                       source=OFFICIAL)
        # The official card's own words survive the mounting at 1:1.
        text = " ".join(fd.pdf_text(letter).split()).upper()
        self.assertIn("1. R. THUMB", text)
        self.assertIn(fd.MARKER_REVISION.upper(), text)

    def test_letter_page_is_the_card_plus_trim_marks_only(self):
        letter = fd.build_official_pdf(self.path("letter.pdf"), letter=True,
                                       source=OFFICIAL)
        text = " ".join(fd.pdf_text(letter).split()).upper()
        self.assertIn("PRINT AT 100%", text)
        self.assertIn("CLARKSBURG, WV 26306", text)


class TestHardRequirement2Resolution(TempDirCase):
    """300 DPI print readiness; the 72-DPI downsample must be rejected."""

    def test_official_card_rasterises_to_2400px(self):
        pdf = fd.build_official_pdf(self.path("card.pdf"), source=OFFICIAL)
        self.assertEqual(fd.raster_dimensions(pdf, 300), (2400, 2400))

    def test_official_embedded_rasters_are_at_least_300_dpi(self):
        for _, _, xppi, yppi in fd.embedded_image_dpi(OFFICIAL):
            self.assertGreaterEqual(min(xppi, yppi), 300)

    def test_raster_mode_embeds_300_dpi_images(self):
        pdf = fd.build_raster_pdf(self.path("raster.pdf"), source=OFFICIAL)
        images = fd.embedded_image_dpi(pdf)
        self.assertEqual(len(images), fd.OFFICIAL_PAGES)
        for w, h, xppi, yppi in images:
            self.assertEqual((w, h), (2400, 2400))
            self.assertGreaterEqual(min(xppi, yppi), 300)

    def test_raster_mode_refuses_below_300_dpi(self):
        with self.assertRaises(ValueError):
            fd.build_raster_pdf(self.path("bad.pdf"), dpi=72, source=OFFICIAL)

    def test_72_dpi_downsample_fails_the_gate(self):
        """The historically rejected build must FAIL, not squeak through."""
        bad = self._build_72dpi_card(self.path("bad72.pdf"))
        images = fd.embedded_image_dpi(bad)
        self.assertTrue(images)
        self.assertLess(min(min(x, y) for _, _, x, y in images), 300)
        ok, results = fd.verify_pdf(bad, check_fields=False)
        self.assertFalse(ok)
        dpi_checks = [r for r in results if "DPI" in r[0] and "raster" in r[0]]
        self.assertTrue(dpi_checks and not dpi_checks[0][1],
                        "the DPI gate did not flag the 72-DPI build")

    def _build_72dpi_card(self, out):
        """Reproduce the rejected 576x576 @ 72 ppi build for the gate to catch."""
        from reportlab.pdfgen import canvas as rl
        stem = os.path.join(self.tmp, "low")
        fd.run(["pdftoppm", "-r", "72", "-png", "-gray", OFFICIAL, stem])
        pngs = sorted(f for f in os.listdir(self.tmp) if f.startswith("low"))
        c = rl.Canvas(out, pagesize=(fd.CARD_SIZE, fd.CARD_SIZE))
        for png in pngs:
            c.drawImage(os.path.join(self.tmp, png), 0, 0,
                        width=fd.CARD_SIZE, height=fd.CARD_SIZE)
            c.showPage()
        c.save()
        return out


class TestHardRequirement3Naming(unittest.TestCase):
    """FD-258_<LASTNAME>_<FIRSTNAME>.pdf"""

    def test_default_filename(self):
        self.assertEqual(fd.default_filename("Gros", "Marcelo"),
                         "FD-258_GROS_MARCELO.pdf")

    def test_filename_is_sanitised(self):
        self.assertEqual(fd.default_filename("O'Neill-Smith", "José Luis"),
                         "FD-258_O-NEILL-SMITH_JOS-LUIS.pdf")

    def test_blank_card_gets_a_safe_default(self):
        self.assertEqual(fd.default_filename(None, None),
                         "FD-258_BLANK_CARD.pdf")

    def test_cli_derives_the_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out = cli("generate", "--lastname", "Gros",
                          "--firstname", "Marcelo", "--outdir", tmp)
            self.assertEqual(rc, 0, out)
            self.assertTrue(os.path.isfile(
                os.path.join(tmp, "FD-258_GROS_MARCELO.pdf")), out)


class TestCardContent(TempDirCase):
    """The official FD-258's own fields and layout."""

    @classmethod
    def setUpClass(cls):
        cls._d = tempfile.TemporaryDirectory()
        cls.pdf = fd.build_official_pdf(os.path.join(cls._d.name, "card.pdf"),
                                        source=OFFICIAL)
        cls.text = " ".join(fd.pdf_text(cls.pdf).split()).upper()

    @classmethod
    def tearDownClass(cls):
        cls._d.cleanup()

    def test_official_markers(self):
        for marker in (fd.MARKER_REVISION, fd.MARKER_OMB, fd.MARKER_AGENCY):
            self.assertIn(marker.upper(), self.text)

    def test_back_page_is_present(self):
        for line in ("UNITED STATES DEPARTMENT OF JUSTICE",
                     "CJIS DIVISION/CLARKSBURG, WV 26306",
                     "THIS CARD FOR USE BY:"):
            self.assertIn(line, self.text)

    def test_admin_blocks(self):
        for label in ("APPLICANT", "LEAVE BLANK", "YOUR NO.", "OCA",
                      "UNIVERSAL CONTROL NO.", "UCN"):
            self.assertIn(label, self.text)

    def test_personal_data_fields(self):
        for label in ("LAST NAME", "FIRST NAME", "MIDDLE NAME", "ALIASES",
                      "RESIDENCE OF PERSON FINGERPRINTED", "DATE OF BIRTH",
                      "SEX", "RACE", "HGT.", "WGT.", "EYES", "HAIR",
                      "PLACE OF BIRTH", "SIGNATURE OF PERSON FINGERPRINTED",
                      "EMPLOYER AND ADDRESS", "REASON FINGERPRINTED",
                      "SIGNATURE OF OFFICIAL TAKING FINGERPRINTS",
                      "SOCIAL SECURITY NO."):
            self.assertIn(label, self.text)

    def test_ten_rolled_impression_blocks(self):
        for label in ("R. THUMB", "R. INDEX", "R. MIDDLE", "R. RING",
                      "R. LITTLE", "L. THUMB", "L. INDEX", "L. MIDDLE",
                      "L. RING", "L. LITTLE"):
            self.assertIn(label, self.text)

    def test_simultaneous_impression_blocks(self):
        self.assertIn("LEFT FOUR FINGERS TAKEN SIMULTANEOUSLY", self.text)
        self.assertIn("RIGHT FOUR FINGERS TAKEN SIMULTANEOUSLY", self.text)

    def test_blank_by_default(self):
        """No stray values: a blank card carries the official labels only."""
        self.assertNotIn("MARCELO", self.text)

    def test_prefill_overlay(self):
        pdf = fd.build_official_pdf(self.path("filled.pdf"), {
            "lastname": "Gros", "firstname": "Marcelo", "dob": "03 14 1988",
            "sex": "M", "race": "W", "height": "5-11", "weight": "175",
            "eyes": "BRO", "hair": "BLK", "pob": "BUENOS AIRES, AR",
            "residence": "123 MAIN ST", "oca": "REQ-4471", "ori": "WVFBI0000",
        }, source=OFFICIAL)
        text = " ".join(fd.pdf_text(pdf).split()).upper()
        for value in ("GROS", "MARCELO", "03 14 1988", "BUENOS AIRES, AR",
                      "123 MAIN ST", "REQ-4471", "WVFBI0000"):
            self.assertIn(value, text)
        # ... and the official card is still underneath it.
        self.assertIn(fd.MARKER_REVISION.upper(), text)

    def test_prefill_aliases_map_onto_official_fields(self):
        resolved = fd.resolve_data({"contributor": "ACME CORP",
                                    "date_signed": "08 24 2026"})
        self.assertEqual(resolved,
                         {"employer": "ACME CORP",
                          "date_fingerprinted": "08 24 2026"})

    def test_prefill_ignores_unknown_and_empty_values(self):
        self.assertEqual(fd.resolve_data({"lastname": "", "nonsense": "x"}), {})

    def test_signature_boxes_are_never_prefilled(self):
        """Signatures must be made in ink, so no overlay targets them."""
        for key in fd.OVERLAY_FIELDS:
            self.assertNotIn("signature", key)

    def test_raster_build_keeps_a_text_layer(self):
        pdf = fd.build_raster_pdf(self.path("raster.pdf"), source=OFFICIAL)
        text = " ".join(fd.pdf_text(pdf).split()).upper()
        self.assertIn(fd.MARKER_AGENCY.upper(), text)
        self.assertIn("LAST NAME", text)


class TestVerifyCommand(TempDirCase):
    """The QA gate itself: PASS/FAIL per check, non-zero exit on any FAIL."""

    def test_official_card_passes(self):
        pdf = fd.build_official_pdf(self.path("card.pdf"), source=OFFICIAL)
        rc, out = cli("verify", "--file", pdf)
        self.assertEqual(rc, 0, out)
        self.assertIn("RESULT: PASS", out)
        self.assertNotIn("[FAIL]", out)

    def test_raw_official_pdf_passes(self):
        rc, out = cli("verify", "--file", OFFICIAL)
        self.assertEqual(rc, 0, out)
        self.assertIn("RESULT: PASS", out)

    def test_raster_card_passes(self):
        pdf = fd.build_raster_pdf(self.path("raster.pdf"), source=OFFICIAL)
        rc, out = cli("verify", "--file", pdf)
        self.assertEqual(rc, 0, out)
        self.assertIn("RESULT: PASS", out)

    def test_letter_passes_with_flag(self):
        pdf = fd.build_official_pdf(self.path("letter.pdf"), letter=True,
                                    source=OFFICIAL)
        rc, out = cli("verify", "--file", pdf, "--letter")
        self.assertEqual(rc, 0, out)
        self.assertIn("RESULT: PASS", out)

    def test_letter_fails_when_checked_as_a_card(self):
        pdf = fd.build_official_pdf(self.path("letter.pdf"), letter=True,
                                    source=OFFICIAL)
        rc, out = cli("verify", "--file", pdf)
        self.assertEqual(rc, 1, out)
        self.assertIn("RESULT: FAIL", out)

    def test_wrong_page_size_fails(self):
        from reportlab.pdfgen import canvas as rl
        bad = self.path("a4ish.pdf")
        c = rl.Canvas(bad, pagesize=(595.0, 842.0))
        c.showPage()
        c.save()
        rc, out = cli("verify", "--file", bad)
        self.assertEqual(rc, 1, out)
        self.assertIn("[FAIL]", out)

    def test_a_hand_drawn_lookalike_fails_the_marker_gate(self):
        """
        A card that is the right size and DPI but is NOT the FBI's document
        must be rejected -- this is the whole point of the marker gate.
        """
        from reportlab.pdfgen import canvas as rl
        fake = self.path("handdrawn.pdf")
        c = rl.Canvas(fake, pagesize=(fd.CARD_SIZE, fd.CARD_SIZE))
        for _ in range(fd.OFFICIAL_PAGES):
            c.setFont("Helvetica", 10)
            c.drawString(20, 540, "FINGERPRINT CARD")
            c.drawString(20, 520, "LAST NAME   FIRST NAME   MIDDLE NAME")
            c.showPage()
        c.save()
        ok, results = fd.verify_pdf(fake, check_fields=False)
        self.assertFalse(ok)
        marker = [r for r in results if "official FBI card markers" in r[0]]
        self.assertTrue(marker and not marker[0][1],
                        "the marker gate did not flag a hand-drawn card")
        rc, out = cli("verify", "--file", fake, "--no-fields")
        self.assertEqual(rc, 1, out)
        self.assertIn("RESULT: FAIL", out)

    def test_single_page_extract_fails_the_page_count_gate(self):
        """Losing the FBI/DOJ back page must be caught."""
        from pypdf import PdfReader, PdfWriter
        one = self.path("front-only.pdf")
        writer = PdfWriter()
        writer.add_page(PdfReader(OFFICIAL).pages[0])
        with open(one, "wb") as fh:
            writer.write(fh)
        ok, results = fd.verify_pdf(one, check_fields=False)
        self.assertFalse(ok)
        pages = [r for r in results if "official front + back" in r[0]]
        self.assertTrue(pages and not pages[0][1])

    def test_missing_file_is_a_failure_not_a_crash(self):
        rc, out = cli("verify", "--file", self.path("nope.pdf"))
        self.assertEqual(rc, 1, out)
        self.assertIn("RESULT: FAIL", out)

    def test_generate_with_verify_flag(self):
        rc, out = cli("generate", "--out", self.path("c.pdf"), "--verify")
        self.assertEqual(rc, 0, out)
        self.assertIn("RESULT: PASS", out)


class TestShippedSample(unittest.TestCase):
    """samples/FD-258_GROS_MARCELO.pdf must exist and pass the gate."""

    def setUp(self):
        if not os.path.isfile(SAMPLE):
            self.skipTest("sample not built yet; run `make sample`")

    def test_sample_passes_the_gate(self):
        rc, out = cli("verify", "--file", SAMPLE)
        self.assertEqual(rc, 0, out)
        self.assertIn("RESULT: PASS", out)

    def test_sample_is_576_square_two_pages(self):
        w, h, pages = fd.pdf_page_size(SAMPLE)
        self.assertEqual((w, h), (576.0, 576.0))
        self.assertEqual(pages, fd.OFFICIAL_PAGES)

    def test_sample_is_the_official_card(self):
        text = " ".join(fd.pdf_text(SAMPLE).split()).upper()
        self.assertIn(fd.MARKER_REVISION.upper(), text)
        self.assertIn(fd.MARKER_OMB.upper(), text)
        self.assertIn(fd.MARKER_AGENCY.upper(), text)

    def test_sample_is_300_dpi_ready(self):
        self.assertEqual(fd.raster_dimensions(SAMPLE, 300), (2400, 2400))
        for w, h, xppi, yppi in fd.embedded_image_dpi(SAMPLE):
            self.assertGreaterEqual(min(xppi, yppi), 300)

    def test_sample_is_blank(self):
        text = " ".join(fd.pdf_text(SAMPLE).split()).upper()
        self.assertIn("LAST NAME", text)
        self.assertNotIn("MARCELO", text)   # named for the client, but blank


if __name__ == "__main__":
    unittest.main(verbosity=2)
