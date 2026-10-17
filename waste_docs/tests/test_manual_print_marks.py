from __future__ import annotations

import json
from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from waste_docs.models import PrintFileMark
from waste_docs.services.manual_print_marks import file_row_key, mark_row_printed, printed_row_keys


class ManualPrintMarksTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="printuser", password="pass")
        self.client = Client()
        self.client.force_login(self.user)
        self.drive_date = date(2026, 3, 1)
        self.row_key = file_row_key(
            kind="xlsx",
            media_rel="pruvodky/test.xlsx",
        )

    def test_mark_row_printed_persists(self):
        mark_row_printed(self.user, self.drive_date, self.row_key)
        self.assertIn(self.row_key, printed_row_keys(self.user, self.drive_date))

    def test_mark_printed_api(self):
        url = reverse("waste_docs:mark_file_row_printed")
        response = self.client.post(
            url,
            data=json.dumps({"date": self.drive_date.isoformat(), "row_key": self.row_key}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PrintFileMark.objects.filter(
                user=self.user,
                drive_date=self.drive_date,
                row_key=self.row_key,
            ).exists()
        )

    def test_mark_printed_requires_login(self):
        anon = Client()
        url = reverse("waste_docs:mark_file_row_printed")
        response = anon.post(
            url,
            data=json.dumps({"date": self.drive_date.isoformat(), "row_key": self.row_key}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)
