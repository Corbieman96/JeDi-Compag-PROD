from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from waste_docs.services.reports.xlsx_basic_pdf import BasicXlsxPdfError
from waste_docs.services.reports.xlsx_to_pdf import (
    XlsxToPdfError,
    _convert_xlsx_to_pdf_file,
    print_url_for_media_rel,
    validate_print_media_rel,
)


class XlsxToPdfValidationTests(SimpleTestCase):
    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_rejects_path_traversal(self):
        with self.assertRaises(XlsxToPdfError):
            validate_print_media_rel("../secret.xlsx")


class PrintUrlTests(SimpleTestCase):
    def test_print_url_contains_rel(self):
        url = print_url_for_media_rel("pruvodky/test.xlsx")
        self.assertIn("rel=pruvodky%2Ftest.xlsx", url)


class XlsxToPdfConvertTests(TestCase):
    def test_cache_path_used_when_fresh(self):
        from waste_docs.services.reports import xlsx_to_pdf as mod

        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            source = media / "pruvodky" / "a.xlsx"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"xlsx")
            cache = media / "print_cache" / "pruvodky" / "a.xlsx.pdf"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(b"%PDF-1.4")
            with override_settings(MEDIA_ROOT=media):
                with patch.object(mod, "_convert_xlsx_to_pdf_file") as convert:
                    result = mod.convert_xlsx_to_pdf(source, media_rel="pruvodky/a.xlsx")
                    convert.assert_not_called()
                    self.assertEqual(result, cache)

    def test_falls_back_to_libreoffice_when_excel_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "pruvodky" / "a.xlsx"
            dest = Path(tmp) / "print_cache" / "pruvodky" / "a.xlsx.pdf"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"xlsx")
            with patch(
                "waste_docs.services.reports.xlsx_to_pdf._convert_with_excel_com",
                side_effect=XlsxToPdfError("excel missing"),
            ):
                with patch(
                    "waste_docs.services.reports.xlsx_to_pdf._convert_with_libreoffice",
                ) as libre:
                    _convert_xlsx_to_pdf_file(source, dest)
                    libre.assert_called_once_with(source, dest)

    def test_raises_when_all_converters_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "a.xlsx"
            dest = Path(tmp) / "a.pdf"
            source.write_bytes(b"xlsx")
            with patch(
                "waste_docs.services.reports.xlsx_to_pdf._convert_with_excel_com",
                side_effect=XlsxToPdfError("excel missing"),
            ):
                with patch(
                    "waste_docs.services.reports.xlsx_to_pdf._convert_with_libreoffice",
                    side_effect=XlsxToPdfError("libre missing"),
                ):
                    with patch(
                        "waste_docs.services.reports.xlsx_basic_pdf.convert_xlsx_to_basic_pdf",
                        side_effect=BasicXlsxPdfError("basic missing"),
                    ):
                        with self.assertRaises(XlsxToPdfError) as ctx:
                            _convert_xlsx_to_pdf_file(source, dest)
                        self.assertIn("setup_print_converter", str(ctx.exception))
