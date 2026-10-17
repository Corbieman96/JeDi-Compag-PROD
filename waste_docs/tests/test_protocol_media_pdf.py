"""PDF protokolu přes login view — funguje i při DEBUG=False."""

from __future__ import annotations

import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from waste_docs.services.reports.protocol_media_pdf import (
    ProtocolMediaPdfError,
    normalize_protocol_pdf_rel,
    protocol_pdf_url_for_media_rel,
)
from waste_docs.services.ride_bulk_actions import _file_row


class ProtocolMediaPdfUrlTests(TestCase):
    def test_url_points_to_login_view_not_media(self):
        url = protocol_pdf_url_for_media_rel("protokoly/protokol_skupina_test.pdf")
        self.assertIn("/waste-docs/print/protocol-media.pdf", url)
        self.assertIn("rel=protokoly%2Fprotokol_skupina_test.pdf", url)
        self.assertNotIn("/media/", url)

    def test_rejects_path_traversal(self):
        with self.assertRaises(ProtocolMediaPdfError):
            normalize_protocol_pdf_rel("../secret.pdf")

    def test_rejects_non_pdf(self):
        with self.assertRaises(ProtocolMediaPdfError):
            normalize_protocol_pdf_rel("protokoly/x.xlsx")

    def test_file_row_rewrites_protocol_urls(self):
        row = _file_row(
            kind="protocol",
            label="Protokol",
            url="/media/protokoly/a.pdf",
            media_rel="protokoly/a.pdf",
        )
        self.assertIn("media-file", row["url"])
        self.assertEqual(row["url"], row["print_url"])
        self.assertNotIn("/media/", row["url"])

    def test_file_row_protocol_xlsx_does_not_raise(self):
        row = _file_row(
            kind="protocol",
            label="Protokol",
            url="/media/protokoly/protokol_den.xlsx",
            media_rel="protokoly/protokol_den.xlsx",
        )
        self.assertIn("media-file", row["url"])
        self.assertIn("as-pdf", row["print_url"])
        self.assertNotIn("/media/", row["url"])


@override_settings(DEBUG=False)
class ProtocolMediaPdfServeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("proto_pdf_user", password="pw", is_superuser=True)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.media = Path(self.tmp.name)
        (self.media / "protokoly").mkdir(parents=True)
        self.pdf = self.media / "protokoly" / "protokol_skupina_2026-09-30_rz26_rid17.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 test protocol")

    def test_authenticated_gets_pdf_when_debug_false(self):
        client = Client()
        client.force_login(self.user)
        url = reverse("waste_docs:protocol_media_pdf")
        with override_settings(MEDIA_ROOT=self.media, DEBUG=False):
            response = client.get(url, {"rel": "protokoly/protokol_skupina_2026-09-30_rz26_rid17.pdf"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4 test protocol")

    def test_anonymous_redirects_to_login(self):
        client = Client()
        url = reverse("waste_docs:protocol_media_pdf")
        with override_settings(MEDIA_ROOT=self.media, DEBUG=False):
            response = client.get(url, {"rel": "protokoly/protokol_skupina_2026-09-30_rz26_rid17.pdf"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_missing_file_is_404(self):
        client = Client()
        client.force_login(self.user)
        url = reverse("waste_docs:protocol_media_pdf")
        with override_settings(MEDIA_ROOT=self.media, DEBUG=False):
            response = client.get(url, {"rel": "protokoly/neexistuje.pdf"})
        self.assertEqual(response.status_code, 404)
