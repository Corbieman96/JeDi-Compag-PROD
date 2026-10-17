"""Sloučený PDF balík pro hromadný tisk."""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from waste_docs.services.reports.bulk_merged_print_pdf import (
    BULK_MERGED_CACHE_SUBDIR,
    build_merged_print_pdf_bytes,
    filter_file_rows_for_print_kind,
)


def _minimal_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        writer.write(fh)


class BulkMergedPrintPdfTests(TestCase):
    def test_filter_file_rows_by_kind(self):
        rows = [
            {"kind": "xlsx", "print_url": "/x", "url": "/x"},
            {"kind": "zpo", "print_url": "/z", "url": "/z"},
        ]
        out = filter_file_rows_for_print_kind(rows, "zpo")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["kind"], "zpo")

    def test_filter_all_excludes_protocol(self):
        rows = [
            {"kind": "xlsx", "print_url": "/x", "url": "/x"},
            {"kind": "protocol", "print_url": "/p", "url": "/p"},
            {"kind": "protocol_notes", "print_url": "/n", "url": "/n"},
            {"kind": "zpo", "print_url": "/z", "url": "/z"},
            {"kind": "pio", "print_url": "/i", "url": "/i"},
        ]
        out = filter_file_rows_for_print_kind(rows, "all")
        kinds = {row["kind"] for row in out}
        self.assertEqual(kinds, {"xlsx", "zpo"})

    def test_filter_all_with_protocol_includes_protocol(self):
        rows = [
            {"kind": "xlsx", "print_url": "/x", "url": "/x"},
            {"kind": "protocol", "print_url": "/p", "url": "/p"},
            {"kind": "protocol_notes", "print_url": "/n", "url": "/n"},
            {"kind": "zpo", "print_url": "/z", "url": "/z"},
            {"kind": "pio", "print_url": "/i", "url": "/i"},
        ]
        out = filter_file_rows_for_print_kind(rows, "all_with_protocol")
        kinds = {row["kind"] for row in out}
        self.assertEqual(kinds, {"xlsx", "protocol", "zpo"})

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_build_merged_pdf_from_two_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            pdf1 = media / "zpo" / "a.pdf"
            pdf2 = media / "zpo" / "b.pdf"
            _minimal_pdf(pdf1)
            _minimal_pdf(pdf2)
            rows = [
                {
                    "kind": "zpo",
                    "label": "A",
                    "url": "/media/zpo/a.pdf",
                    "path": str(pdf1),
                    "print_url": "/media/zpo/a.pdf",
                },
                {
                    "kind": "zpo",
                    "label": "B",
                    "url": "/media/zpo/b.pdf",
                    "path": str(pdf2),
                    "print_url": "/media/zpo/b.pdf",
                },
            ]
            with override_settings(MEDIA_ROOT=media):
                payload = build_merged_print_pdf_bytes(rows, print_kind="all")
            self.assertTrue(payload.startswith(b"%PDF"))


class BulkMergedPrintPdfEmptyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="empty_merge", password="pw-123456"
        )
        self.client.force_login(self.user)
        self.url = reverse("waste_docs:bulk_merged_print_pdf")
        self.day = date(2026, 6, 22)

    def test_empty_scope_returns_plain_error_not_404_html(self):
        response = self.client.post(
            self.url,
            {"date": self.day.isoformat(), "print_kind": "all", "vehicle_rz_id": "99999"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode(), "Není nic k tisku.")

    def test_empty_scope_stream_returns_json_error(self):
        response = self.client.post(
            self.url,
            {
                "date": self.day.isoformat(),
                "print_kind": "all",
                "vehicle_rz_id": "99999",
                "stream": "1",
            },
        )
        self.assertEqual(response.status_code, 200)
        first_line = b"".join(response.streaming_content).split(b"\n", 1)[0].decode()
        response.close()
        payload = json.loads(first_line)
        self.assertEqual(payload["type"], "error")
        self.assertEqual(payload["message"], "Není nic k tisku.")


class BulkMergedPdfDownloadTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dl_user", password="pw-123456"
        )
        self.client.force_login(self.user)

    def test_download_serves_existing_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            name = "merged_" + "a" * 32 + ".pdf"
            target = media / "print_cache" / BULK_MERGED_CACHE_SUBDIR / name
            _minimal_pdf(target)
            url = reverse("waste_docs:bulk_merged_print_download", args=[name])
            with override_settings(MEDIA_ROOT=media):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp["Content-Type"], "application/pdf")
                b"".join(resp.streaming_content)
                resp.close()

    def test_download_rejects_invalid_name(self):
        url = reverse("waste_docs:bulk_merged_print_download", args=["evil.pdf"])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_download_missing_file_is_404(self):
        name = "merged_" + "b" * 32 + ".pdf"
        url = reverse("waste_docs:bulk_merged_print_download", args=[name])
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=Path(tmp)):
                resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_download_requires_login(self):
        self.client.logout()
        name = "merged_" + "c" * 32 + ".pdf"
        url = reverse("waste_docs:bulk_merged_print_download", args=[name])
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (302, 403))
