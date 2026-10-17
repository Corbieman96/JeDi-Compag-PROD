from io import BytesIO
from unittest.mock import MagicMock, patch

from django.core.files.storage import default_storage
from django.test import SimpleTestCase, override_settings

from waste_docs.models import Pruvodka


def _minimal_pdf_bytes() -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=400, height=600)
    bio = BytesIO()
    writer.write(bio)
    return bio.getvalue()


def _pdf_extract_text(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    return "".join(page.extract_text() or "" for page in reader.pages)


class ZpoStampTests(SimpleTestCase):
    def test_zpo_stamp_layout_uses_template_font_size(self):
        from waste_docs.zpo_instance_generator import ZPO_SND_FONT_PT, _zpo_stamp_layout

        x, y, fs = _zpo_stamp_layout(595.0, 842.0, "0000042-2026-3", lambda s, f: len(s) * 5.0)
        self.assertEqual(fs, ZPO_SND_FONT_PT)
        self.assertEqual(fs, 10.0)
        self.assertGreater(x, 0)
        self.assertEqual(y, 22.0)

    def test_stamp_snd_overlay_embeds_visible_text(self):
        from waste_docs.zpo_instance_generator import _stamp_snd_overlay

        snd = "0000042-2026-3"
        with patch("reportlab.pdfgen.canvas.Canvas.setFont") as mock_set_font:
            out = _stamp_snd_overlay(_minimal_pdf_bytes(), snd)
            mock_set_font.assert_called_with("Helvetica", 10.0)
        self.assertIn(snd, _pdf_extract_text(out))

    def test_build_pdf_bytes_falls_back_when_fitz_unavailable(self):
        from waste_docs.zpo_instance_generator import _build_pdf_bytes_from_bytes

        item = MagicMock()
        item.snd_cislo_listu = "0000099-2026-1"
        with patch(
            "waste_docs.zpo_instance_generator._stamp_snd_fitz",
            side_effect=ImportError("DLL load failed"),
        ):
            out = _build_pdf_bytes_from_bytes(_minimal_pdf_bytes(), item)
        self.assertIn("0000099-2026-1", _pdf_extract_text(out))


class DisplayZpoFileTests(SimpleTestCase):
    def test_no_template_fallback_when_snd_present_but_instance_missing(self):
        from waste_docs.models import Pruvodka
        from waste_docs.zpo_resolved import display_zpo_file_for_pruvodka

        ride = MagicMock(spec=Pruvodka)
        ride.zpo_instance_file = None
        ride.snd_cislo_listu = "0000001-2026-1"
        self.assertIsNone(display_zpo_file_for_pruvodka(ride))

    def test_returns_instance_when_file_exists(self):
        from waste_docs.models import Pruvodka
        from waste_docs.zpo_resolved import display_zpo_file_for_pruvodka

        ride = MagicMock(spec=Pruvodka)
        ride.zpo_instance_file = MagicMock()
        ride.zpo_instance_file.name = "pruvodky/zpo_instance/test.pdf"
        ride.snd_cislo_listu = "0000002-2026-1"
        with patch.object(default_storage, "exists", return_value=True):
            result = display_zpo_file_for_pruvodka(ride)
        self.assertIs(result, ride.zpo_instance_file)


class ZpoInstanceCleanupTests(SimpleTestCase):
    @override_settings(MEDIA_ROOT="/tmp/jedis-zpo-cleanup-test")
    def test_cleanup_orphans_for_pruvodka_keeps_canonical_file(self):
        from pathlib import Path

        from waste_docs.services.zpo_instance_cleanup import cleanup_zpo_instance_orphans_for_pruvodka

        base = Path("/tmp/jedis-zpo-cleanup-test/pruvodky/zpo_instance")
        base.mkdir(parents=True, exist_ok=True)
        keep = base / "575_0000290-2026-1.pdf"
        orphan = base / "575_0000290-2026-1_krV8Mwi.pdf"
        keep.write_bytes(b"%PDF-1")
        orphan.write_bytes(b"%PDF-2")

        deleted = cleanup_zpo_instance_orphans_for_pruvodka(
            575,
            keep_name="pruvodky/zpo_instance/575_0000290-2026-1.pdf",
        )
        self.assertEqual(deleted, 1)
        self.assertTrue(keep.is_file())
        self.assertFalse(orphan.exists())

        keep.unlink(missing_ok=True)
        base.rmdir()
