"""Reset značky Vytištěno po regeneraci souborů."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from waste_docs.models import PrintFileMark
from waste_docs.services.manual_print_marks import (
    clear_pruvodka_print_marks,
    clear_protocol_marks_for_date,
    day_protocol_row_key,
    file_row_key,
    mark_row_printed,
    printed_row_keys,
    row_keys_for_pruvodka,
)
from waste_docs.models import Pruvodka


class PrintMarkResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mark_reset", password="x")
        self.other = User.objects.create_user(username="mark_other", password="x")
        self.drive_date = date(2032, 7, 1)

    def test_clear_protocol_marks_for_date_all_users(self):
        key = day_protocol_row_key(self.drive_date)
        mark_row_printed(self.user, self.drive_date, key)
        mark_row_printed(self.other, self.drive_date, key)
        clear_protocol_marks_for_date(self.drive_date)
        self.assertEqual(printed_row_keys(self.user, self.drive_date), set())
        self.assertEqual(printed_row_keys(self.other, self.drive_date), set())

    def test_clear_pruvodka_print_marks_xlsx(self):
        ride = Pruvodka(pk=501, drive_date=self.drive_date)
        ride.generated_file.name = "pruvodky/pruvodka_test.xlsx"
        key = file_row_key(kind="xlsx", media_rel="pruvodky/pruvodka_test.xlsx")
        mark_row_printed(self.user, self.drive_date, key)
        self.assertIn(key, row_keys_for_pruvodka(ride))
        clear_pruvodka_print_marks(ride)
        self.assertFalse(PrintFileMark.objects.filter(drive_date=self.drive_date, row_key=key).exists())
