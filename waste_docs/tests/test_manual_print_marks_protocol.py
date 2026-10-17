from __future__ import annotations

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from waste_docs.models import PrintFileMark
from waste_docs.services.manual_print_marks import (
    day_protocol_row_key,
    mark_row_printed,
    migrate_legacy_protocol_marks,
    printed_row_keys,
)


class ProtocolPrintMarksTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="protuser", password="pass")
        self.drive_date = date(2026, 6, 10)

    def test_stable_day_protocol_key(self):
        key = day_protocol_row_key(self.drive_date)
        self.assertEqual(key, "protocol:day:2026-06-10")
        mark_row_printed(self.user, self.drive_date, key)
        self.assertIn(key, printed_row_keys(self.user, self.drive_date))

    def test_migrate_legacy_protocol_mark(self):
        legacy = "protocol:protokoly/protokol_den_2026-06-10.xlsx"
        mark_row_printed(self.user, self.drive_date, legacy)
        migrate_legacy_protocol_marks(self.user, self.drive_date)
        stable = day_protocol_row_key(self.drive_date)
        self.assertIn(stable, printed_row_keys(self.user, self.drive_date))
        self.assertFalse(PrintFileMark.objects.filter(row_key=legacy).exists())
