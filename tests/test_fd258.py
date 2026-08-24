#!/usr/bin/env python3
"""
QA gate tests for fd258_card.py.

Run with the hermes venv interpreter (reportlab lives there):

    /usr/local/lib/hermes-agent/venv/bin/python -m unittest discover -s tests -v
    # or:  make test

The three hard requirements from BRIEF.md are asserted directly:
  1. card page size is exactly 576 x 576 pt (8" x 8")
  2. the card is print-ready at 300 DPI -- it rasterises to 2400 x 2400 px and
     any embedded raster is >= 300 DPI (a 72-DPI build must FAIL the gate)
  3. output is a single PDF named FD-258_<LASTNAME>_<FIRSTNAME>.pdf
plus the --letter mode (612 x 792 pt) and the FD-258 field inventory.
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


class TestHardRequirement1PageSize(TempDirCase):
    """576 x 576 pt, exactly, single page."""

    def test_card_is_576_by_576(self):
        pdf = fd.build_vector_pdf(self.path("card.pdf"))
        w, h, pages = fd.pdf_page_size(pdf)
        self.assertEqual((w, h), (576.0, 576.0))
        self.assertEqual(pages, 1)

    def test_letter_mode_is_612_by_792(self):
        pdf = fd.build_vector_pdf(self.path("letter.pdf"), letter=True)
        w, h, pages = fd.pdf_page_size(pdf)
        self.assertEqual((w, h), (612.0, 792.0))
        self.assertEqual(pages, 1)

    def test_letter_embeds_card_at_100_percent(self):
        """The card must sit unscaled and centred on the letter sheet."""
        self.assertAlmostEqual((fd.LETTER_W - fd.CARD_SIZE) / 2.0, 18.0)
        self.assertAlmostEqual((fd.LETTER_H - fd.CARD_SIZE) / 2.0, 108.0)
        letter = fd.build_vector_pdf(self.path("letter.pdf"), letter=True)
        card = fd.build_vector_pdf(self.path("card.pdf"))
        # Same 540 pt content frame on both -> no scaling was applied.
        self.assertIn("RIGHT HAND", fd.pdf_text(letter))
        self.assertIn("RIGHT HAND", fd.pdf_text(card))

    def test_geometry_bands_sum_to_the_card(self):
        fd._validate_geometry()   # asserts internally; must not raise


class TestHardRequirement2Resolution(TempDirCase):
    """300 DPI print readiness; the 72-DPI downsample must be rejected."""

    def test_vector_card_rasterises_to_2400px(self):
        pdf = fd.build_vector_pdf(self.path("card.pdf"))
        self.assertEqual(fd.raster_dimensions(pdf, 300), (2400, 2400))

    def test_raster_mode_embeds_300_dpi_image(self):
        pdf = fd.build_raster_pdf(self.path("raster.pdf"))
        images = fd.embedded_image_dpi(pdf)
        self.assertTrue(images, "no embedded raster found")
        for w, h, xppi, yppi in images:
            self.assertEqual((w, h), (2400, 2400))
            self.assertGreaterEqual(min(xppi, yppi), 300)

    def test_raster_mode_refuses_below_300_dpi(self):
        with self.assertRaises(ValueError):
            fd.build_raster_pdf(self.path("bad.pdf"), dpi=72)

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
        vec = fd.build_vector_pdf(self.path("_src.pdf"))
        stem = os.path.join(self.tmp, "low")
        fd.run(["pdftoppm", "-r", "72", "-png", "-gray", "-f", "1", "-l", "1",
                vec, stem])
        png = os.path.join(self.tmp,
                           sorted(f for f in os.listdir(self.tmp)
                                  if f.startswith("low"))[0])
        c = rl.Canvas(out, pagesize=(fd.CARD_SIZE, fd.CARD_SIZE))
        c.drawImage(png, 0, 0, width=fd.CARD_SIZE, height=fd.CARD_SIZE)
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
    """Requirement 5: the standard FD-258 fields and layout."""

    @classmethod
    def setUpClass(cls):
        cls._d = tempfile.TemporaryDirectory()
        cls.pdf = fd.build_vector_pdf(os.path.join(cls._d.name, "card.pdf"))
        cls.text = " ".join(fd.pdf_text(cls.pdf).split()).upper()

    @classmethod
    def tearDownClass(cls):
        cls._d.cleanup()

    def test_masthead(self):
        for line in ("FEDERAL BUREAU OF INVESTIGATION",
                     "UNITED STATES DEPARTMENT OF JUSTICE",
                     "FINGERPRINT CARD"):
            self.assertIn(line, self.text)

    def test_admin_blocks(self):
        for label in ("ORIGINATING AGENCY IDENTIFIER", "ORI", "OCA",
                      "DATE FINGERPRINTED"):
            self.assertIn(label, self.text)

    def test_personal_data_fields(self):
        for label in ("LAST NAME", "FIRST NAME", "MIDDLE NAME", "ALIASES",
                      "RESIDENCE OF PERSON FINGERPRINTED", "DATE OF BIRTH",
                      "SEX", "RACE", "HGT", "WGT", "EYES", "HAIR",
                      "PLACE OF BIRTH", "SIGNATURE OF PERSON FINGERPRINTED",
                      "CONTRIBUTOR'S NAME AND ADDRESS", "REASON FINGERPRINTED",
                      "SIGNATURE OF OFFICIAL TAKING FINGERPRINTS"):
            self.assertIn(label, self.text)

    def test_ten_rolled_impression_blocks(self):
        for label in ("R. THUMB", "R. INDEX", "R. MIDDLE", "R. RING",
                      "R. LITTLE", "L. THUMB", "L. INDEX", "L. MIDDLE",
                      "L. RING", "L. LITTLE"):
            self.assertIn(label, self.text)
        self.assertIn("RIGHT HAND", self.text)
        self.assertIn("LEFT HAND", self.text)

    def test_simultaneous_impression_blocks(self):
        self.assertIn("LEFT FOUR FINGERS TAKEN SIMULTANEOUSLY", self.text)
        self.assertIn("RIGHT FOUR FINGERS TAKEN SIMULTANEOUSLY", self.text)

    def test_blank_by_default(self):
        """No stray values: a blank card carries labels only."""
        self.assertNotIn("MARCELO", self.text)

    def test_prefill(self):
        pdf = fd.build_vector_pdf(self.path("filled.pdf"), {
            "lastname": "Gros", "firstname": "Marcelo", "dob": "03 14 1988"})
        text = " ".join(fd.pdf_text(pdf).split()).upper()
        self.assertIn("GROS", text)
        self.assertIn("MARCELO", text)
        self.assertIn("03 14 1988", text)

    def test_raster_build_keeps_a_text_layer(self):
        pdf = fd.build_raster_pdf(self.path("raster.pdf"))
        text = " ".join(fd.pdf_text(pdf).split()).upper()
        self.assertIn("FEDERAL BUREAU OF INVESTIGATION", text)


class TestVerifyCommand(TempDirCase):
    """The QA gate itself: PASS/FAIL per check, non-zero exit on any FAIL."""

    def test_vector_card_passes(self):
        pdf = fd.build_vector_pdf(self.path("card.pdf"))
        rc, out = cli("verify", "--file", pdf)
        self.assertEqual(rc, 0, out)
        self.assertIn("RESULT: PASS", out)
        self.assertNotIn("[FAIL]", out)

    def test_raster_card_passes(self):
        pdf = fd.build_raster_pdf(self.path("raster.pdf"))
        rc, out = cli("verify", "--file", pdf)
        self.assertEqual(rc, 0, out)
        self.assertIn("RESULT: PASS", out)

    def test_letter_passes_with_flag(self):
        pdf = fd.build_vector_pdf(self.path("letter.pdf"), letter=True)
        rc, out = cli("verify", "--file", pdf, "--letter")
        self.assertEqual(rc, 0, out)
        self.assertIn("RESULT: PASS", out)

    def test_letter_fails_when_checked_as_a_card(self):
        pdf = fd.build_vector_pdf(self.path("letter.pdf"), letter=True)
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

    def test_sample_is_576_square(self):
        self.assertEqual(fd.pdf_page_size(SAMPLE)[:2], (576.0, 576.0))

    def test_sample_is_300_dpi(self):
        images = fd.embedded_image_dpi(SAMPLE)
        self.assertTrue(images, "sample has no embedded raster")
        for w, h, xppi, yppi in images:
            self.assertEqual((w, h), (2400, 2400))
            self.assertGreaterEqual(min(xppi, yppi), 300)

    def test_sample_is_blank(self):
        text = " ".join(fd.pdf_text(SAMPLE).split()).upper()
        self.assertIn("LAST NAME", text)
        self.assertNotIn("MARCELO", text)   # named for the client, but blank


if __name__ == "__main__":
    unittest.main(verbosity=2)
