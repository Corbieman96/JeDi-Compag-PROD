"""Stažení generovaných media souborů — funguje i při DEBUG=False."""

from __future__ import annotations

import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from waste_docs.services.reports.media_download import (
    MediaDownloadError,
    media_download_url_for_rel,
    normalize_media_download_rel,
)
from waste_docs.services.ride_bulk_actions import _file_row


class MediaDownloadUrlTests(TestCase):
    def test_url_points_to_login_view_not_media(self):
        url = media_download_url_for_rel("pruvodky/pruvodka_0001649-2026-3.xlsx")
        self.assertIn("/waste-docs/print/media-file/", url)
        self.assertIn("rel=pruvodky%2Fpruvodka_0001649-2026-3.xlsx", url)
        self.assertNotIn("/media/", url)

    def test_rejects_path_traversal(self):
        with self.assertRaises(MediaDownloadError):
            normalize_media_download_rel("../secret.xlsx")

    def test_rejects_disallowed_prefix(self):
        with self.assertRaises(MediaDownloadError):
            normalize_media_download_rel("secrets/x.pdf")

    def test_allows_legacy_pio_prefix(self):
        rel = normalize_media_download_rel("name_subject_pairs/pio/active_pio.pdf")
        self.assertEqual(rel, "name_subject_pairs/pio/active_pio.pdf")

    def test_file_row_rewrites_legacy_pio_urls(self):
        row = _file_row(
            kind="pio",
            label="PIO",
            url="/media/name_subject_pairs/pio/active_pio.pdf",
            media_rel="name_subject_pairs/pio/active_pio.pdf",
        )
        self.assertIn("media-file", row["url"])
        self.assertEqual(row["url"], row["print_url"])
        self.assertNotIn("/media/", row["url"])

    def test_file_row_keeps_url_on_media_download_error(self):
        original = "/media/secrets/not-allowed.pdf"
        row = _file_row(
            kind="pio",
            label="PIO",
            url=original,
            media_rel="secrets/not-allowed.pdf",
        )
        self.assertEqual(row["url"], original)
        self.assertEqual(row["print_url"], original)

    def test_file_row_rewrites_xlsx_open_url(self):
        row = _file_row(
            kind="xlsx",
            label="Průvodka",
            url="/media/pruvodky/a.xlsx",
            media_rel="pruvodky/a.xlsx",
        )
        self.assertIn("media-file", row["url"])
        self.assertNotIn("/media/", row["url"])
        self.assertIn("as-pdf", row["print_url"])

    def test_file_row_rewrites_zpo_urls(self):
        row = _file_row(
            kind="zpo",
            label="ZPO",
            url="/media/pruvodky/zpo_instance/1.pdf",
            media_rel="pruvodky/zpo_instance/1.pdf",
        )
        self.assertIn("media-file", row["url"])
        self.assertEqual(row["url"], row["print_url"])
        self.assertNotIn("/media/", row["url"])


@override_settings(DEBUG=False)
class MediaDownloadServeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("media_dl_user", password="pw", is_superuser=True)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.media = Path(self.tmp.name)
        (self.media / "pruvodky").mkdir(parents=True)
        self.xlsx = self.media / "pruvodky" / "pruvodka_0001649-2026-3.xlsx"
        self.xlsx.write_bytes(b"PK\x03\x04 xlsx-test")

    def test_authenticated_gets_xlsx_when_debug_false(self):
        client = Client()
        client.force_login(self.user)
        url = reverse("waste_docs:media_download")
        with override_settings(MEDIA_ROOT=self.media, DEBUG=False):
            response = client.get(url, {"rel": "pruvodky/pruvodka_0001649-2026-3.xlsx"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "spreadsheet",
            response["Content-Type"],
        )
        self.assertEqual(b"".join(response.streaming_content), b"PK\x03\x04 xlsx-test")

    def test_anonymous_redirects_to_login(self):
        client = Client()
        url = reverse("waste_docs:media_download")
        with override_settings(MEDIA_ROOT=self.media, DEBUG=False):
            response = client.get(url, {"rel": "pruvodky/pruvodka_0001649-2026-3.xlsx"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_missing_file_is_404(self):
        client = Client()
        client.force_login(self.user)
        url = reverse("waste_docs:media_download")
        with override_settings(MEDIA_ROOT=self.media, DEBUG=False):
            response = client.get(url, {"rel": "pruvodky/neexistuje.xlsx"})
        self.assertEqual(response.status_code, 404)
