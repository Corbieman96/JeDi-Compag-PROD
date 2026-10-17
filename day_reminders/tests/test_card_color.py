"""Barva karet denních poznámek."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from day_reminders.models import DayReminder
from day_reminders.services import actions
from day_reminders.card_colors import (
    CardColor,
    card_color_style_dict,
    normalize_card_color,
)
from users.constants import ROLE_DISPECER
from users.services.roles import set_user_role
from waste_docs.services.svoz_dispatch.yard_day_reminder import create_day_reminder_for_svoz_task


class CardColorServiceTests(TestCase):
    def test_normalize_valid_slug(self):
        self.assertEqual(normalize_card_color("blue"), CardColor.BLUE)

    def test_normalize_invalid_falls_back_to_yellow(self):
        self.assertEqual(normalize_card_color("neon"), CardColor.YELLOW)
        self.assertEqual(normalize_card_color(""), CardColor.YELLOW)

    def test_card_color_style_dict_has_css_keys(self):
        style = card_color_style_dict(CardColor.RED)
        self.assertEqual(style["background"], "#fef2f2")
        self.assertIn("border", style)


class CardColorReminderActionsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("card_color_user", password="pw")
        set_user_role(self.user, ROLE_DISPECER)
        self.day = date(2036, 8, 1)

    def test_create_reminder_stores_color(self):
        reminder = actions.create_reminder(
            user=self.user,
            title="Modrá poznámka",
            text="detail",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=self.day,
            card_color=CardColor.BLUE,
        )
        self.assertEqual(reminder.card_color, CardColor.BLUE)

    def test_update_reminder_changes_color(self):
        reminder = actions.create_reminder(
            user=self.user,
            title="Původní",
            text="",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=self.day,
            card_color=CardColor.YELLOW,
        )
        actions.update_reminder(
            reminder.pk,
            title="Původní",
            text="",
            pinned_date=self.day,
            card_color=CardColor.PURPLE,
        )
        reminder.refresh_from_db()
        self.assertEqual(reminder.card_color, CardColor.PURPLE)


class CardColorDashboardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.dispecer = User.objects.create_user("card_color_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.day = date(2036, 8, 2)

    def test_dashboard_renders_card_with_chosen_color(self):
        actions.create_reminder(
            user=self.dispecer,
            title="Červená urgentní",
            text="text",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=self.day,
            card_color=CardColor.RED,
        )
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("core:dashboard") + f"?date={self.day.isoformat()}"
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Červená urgentní")
        self.assertContains(response, "background: #fef2f2")

    def test_post_create_with_color_from_form(self):
        client = Client()
        client.force_login(self.dispecer)
        response = client.post(
            reverse("day_reminders:create"),
            {
                "context_date": self.day.isoformat(),
                "title": "Zelená z formuláře",
                "text": "",
                "kind": "one_off",
                "pinned_date": self.day.isoformat(),
                "card_color": CardColor.GREEN,
            },
        )
        self.assertEqual(response.status_code, 302)
        reminder = DayReminder.objects.get(title="Zelená z formuláře")
        self.assertEqual(reminder.card_color, CardColor.GREEN)

    def test_create_dialog_includes_color_picker(self):
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("core:dashboard") + f"?date={self.day.isoformat()}"
        response = client.get(url)
        self.assertContains(response, "Barva v panelu")
        self.assertContains(response, 'name="card_color"')


class YardDayReminderColorTests(TestCase):
    def setUp(self):
        from catalogs.models import (
            ActivityCatalog,
            NameCatalog,
            NameSubjectProfile,
            NameSubjectWasteSuffixPair,
            SuffixCatalog,
            VehicleKindCatalog,
            WasteTypeCatalog,
        )
        from waste_docs.models import SvozTask

        User = get_user_model()
        self.user = User.objects.create_user("yard_color", password="pw")
        self.target = date(2036, 9, 1)
        self.name = NameCatalog.objects.create(value="Yard color")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="Yard Co")
        self.wt = WasteTypeCatalog.objects.create(code="200302", value="Wt yard color")
        self.suf = SuffixCatalog.objects.create(value="YC")
        self.vk = VehicleKindCatalog.objects.create(name="H", shortcut="H", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
            yard_dispatch_note_enabled=True,
            yard_dispatch_note_title="Urgentní hlášení",
        )
        self.task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.user,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            target_date=self.target,
        )

    def test_yard_auto_reminder_uses_red(self):
        reminder = create_day_reminder_for_svoz_task(
            task=self.task,
            pair=self.pair,
            created_by=self.user,
        )
        self.assertEqual(reminder.card_color, CardColor.RED)
