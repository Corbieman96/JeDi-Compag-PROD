from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from day_reminders.models import DayReminder
from day_reminders.note_print.queryset import reminders_for_print
from day_reminders.note_print.scope import SCOPE_ALL, SCOPE_OTHER, SCOPE_REQUEST
from day_reminders.services import actions

User = get_user_model()


class NoteGroupAndPrintTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="note_print_u", password="x", is_superuser=True)
        self.day = date(2026, 8, 12)

    def test_create_and_update_note_group(self):
        r = actions.create_reminder(
            user=self.user,
            title="CR poznámka",
            text="x",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=self.day,
            note_group=DayReminder.NoteGroup.REQUEST,
        )
        self.assertEqual(r.note_group, DayReminder.NoteGroup.REQUEST)
        actions.update_reminder(r.pk, title="CR poznámka", text="x", pinned_date=self.day, note_group="other")
        r.refresh_from_db()
        self.assertEqual(r.note_group, DayReminder.NoteGroup.OTHER)

    def test_print_scope_filters(self):
        actions.create_reminder(
            user=self.user,
            title="A",
            text="",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=self.day,
            note_group="request",
        )
        actions.create_reminder(
            user=self.user,
            title="B",
            text="",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=self.day,
            note_group="other",
        )
        req = reminders_for_print(self.day, SCOPE_REQUEST)
        other = reminders_for_print(self.day, SCOPE_OTHER)
        all_rows = reminders_for_print(self.day, SCOPE_ALL)
        self.assertEqual([r.title for r in req], ["A"])
        self.assertEqual([r.title for r in other], ["B"])
        self.assertEqual({r.title for r in all_rows}, {"A", "B"})

    def test_print_view_ok(self):
        actions.create_reminder(
            user=self.user,
            title="A",
            text="text",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=self.day,
            note_group="request",
        )
        client = Client()
        client.force_login(self.user)
        url = reverse("day_reminders:print_day")
        resp = client.get(url, {"date": self.day.isoformat(), "scope": "request"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "A")
        self.assertContains(resp, "text")
        self.assertContains(resp, "Požadavek")
