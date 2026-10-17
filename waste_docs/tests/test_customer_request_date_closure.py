"""Uzavření kalendářních dnů pro nové zákaznické požadavky."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    SuffixCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleKindCatalog
from catalogs.services.waste_type_labels import waste_type_combo_metadata
from core.models import AppSettings
from customer_requests.models import CustomerRequest, CustomerRequestDateClosure
from users.constants import ROLE_ADMIN, ROLE_DISPECER, ROLE_ZADAVATEL
from users.services.roles import set_user_role
from waste_docs.forms import CustomerRequestForm
from waste_docs.services.customer_request_date_closure import (
    dashboard_closure_context,
    is_auto_closed,
    is_target_date_closed,
    target_date_closure_error,
    target_date_min_for_user,
    toggle_manual_closure,
)


class CustomerRequestDateClosureServiceTests(TestCase):
    def setUp(self):
        settings = AppSettings.load()
        settings.customer_request_daily_cutoff_time = time(12, 0)
        settings.no_service_on_saturday = False
        settings.no_service_on_sunday = False
        settings.save(
            update_fields=[
                "customer_request_daily_cutoff_time",
                "no_service_on_saturday",
                "no_service_on_sunday",
            ]
        )

        self.day = date(2026, 6, 20)
        tz = timezone.get_current_timezone()
        self.before_cutoff = timezone.make_aware(datetime(2026, 6, 20, 11, 30), tz)
        self.after_cutoff = timezone.make_aware(datetime(2026, 6, 20, 12, 30), tz)

    def test_today_closed_even_before_cutoff(self):
        # Deadline dneška byl (den předem) v cutoff, takže dnešek je uzavřený vždy.
        self.assertTrue(is_auto_closed(self.day, now=self.before_cutoff))
        self.assertTrue(is_auto_closed(self.day, now=self.after_cutoff))

    def test_tomorrow_closes_after_cutoff(self):
        tomorrow = self.day + timedelta(days=1)
        self.assertFalse(is_auto_closed(tomorrow, now=self.before_cutoff))
        self.assertTrue(is_auto_closed(tomorrow, now=self.after_cutoff))
        self.assertFalse(is_auto_closed(self.day + timedelta(days=2), now=self.after_cutoff))

    def test_dashboard_schedules_ui_refresh_before_auto_cutoff(self):
        tomorrow = self.day + timedelta(days=1)
        before = dashboard_closure_context(tomorrow, now=self.before_cutoff)
        after = dashboard_closure_context(tomorrow, now=self.after_cutoff)
        self.assertFalse(before.is_closed)
        self.assertIsNotNone(before.auto_ui_refresh_at)
        self.assertTrue(after.is_closed)
        self.assertIsNone(after.auto_ui_refresh_at)

    def test_dashboard_skips_ui_refresh_for_far_future_day(self):
        far = self.day + timedelta(days=26)
        ctx = dashboard_closure_context(far, now=self.before_cutoff)
        self.assertFalse(ctx.is_closed)
        self.assertIsNone(ctx.auto_ui_refresh_at)

    def test_dashboard_skips_ui_refresh_for_november_from_august(self):
        now = timezone.make_aware(datetime(2026, 8, 18, 11, 0), timezone.get_current_timezone())
        ctx = dashboard_closure_context(date(2026, 11, 11), now=now)
        self.assertFalse(ctx.is_closed)
        self.assertIsNone(ctx.auto_ui_refresh_at)

    def test_auto_closure_is_persistent(self):
        tomorrow = self.day + timedelta(days=1)
        self.assertTrue(is_auto_closed(tomorrow, now=self.after_cutoff))
        tz = timezone.get_current_timezone()
        next_day = timezone.make_aware(datetime(2026, 6, 21, 9, 0), tz)
        day_after = timezone.make_aware(datetime(2026, 6, 22, 9, 0), tz)
        self.assertTrue(is_auto_closed(tomorrow, now=next_day))
        self.assertTrue(is_auto_closed(tomorrow, now=day_after))

    def test_min_date(self):
        User = get_user_model()
        zad = User.objects.create_user("cr_close_min_zad", password="pw")
        set_user_role(zad, ROLE_ZADAVATEL)
        self.assertEqual(
            target_date_min_for_user(zad, now=self.before_cutoff),
            self.day + timedelta(days=1),
        )
        self.assertEqual(
            target_date_min_for_user(zad, now=self.after_cutoff),
            self.day + timedelta(days=2),
        )

    def test_min_date_none_for_admin(self):
        User = get_user_model()
        adm = User.objects.create_user("cr_close_min_adm", password="pw")
        set_user_role(adm, ROLE_ADMIN)
        self.assertIsNone(target_date_min_for_user(adm, now=self.after_cutoff))

    def test_manual_close_future_day(self):
        User = get_user_model()
        disp = User.objects.create_user("cr_close_disp", password="pw")
        set_user_role(disp, ROLE_DISPECER)
        future = self.day + timedelta(days=10)
        toggle_manual_closure(disp, future, now=self.before_cutoff)
        self.assertTrue(is_target_date_closed(future, now=self.before_cutoff))

    def test_manual_open_overrides_auto(self):
        User = get_user_model()
        disp = User.objects.create_user("cr_close_override", password="pw")
        set_user_role(disp, ROLE_DISPECER)
        tomorrow = self.day + timedelta(days=1)
        self.assertTrue(is_target_date_closed(tomorrow, now=self.after_cutoff))
        new_state = toggle_manual_closure(disp, tomorrow, now=self.after_cutoff)
        self.assertFalse(new_state)
        self.assertFalse(is_target_date_closed(tomorrow, now=self.after_cutoff))

    def test_min_date_respects_manual_reopen_after_auto(self):
        User = get_user_model()
        zad = User.objects.create_user("cr_close_min_reopen", password="pw")
        disp = User.objects.create_user("cr_close_min_reopen_d", password="pw")
        set_user_role(zad, ROLE_ZADAVATEL)
        set_user_role(disp, ROLE_DISPECER)
        tomorrow = self.day + timedelta(days=1)
        self.assertEqual(
            target_date_min_for_user(zad, now=self.after_cutoff),
            self.day + timedelta(days=2),
        )
        toggle_manual_closure(disp, tomorrow, now=self.after_cutoff)
        self.assertEqual(
            target_date_min_for_user(zad, now=self.after_cutoff),
            tomorrow,
        )

    def test_toggle_reopen_then_close(self):
        User = get_user_model()
        disp = User.objects.create_user("cr_close_toggle", password="pw")
        set_user_role(disp, ROLE_DISPECER)
        future = self.day + timedelta(days=10)
        self.assertTrue(toggle_manual_closure(disp, future, now=self.before_cutoff))
        self.assertTrue(is_target_date_closed(future, now=self.before_cutoff))
        self.assertFalse(toggle_manual_closure(disp, future, now=self.before_cutoff))
        self.assertFalse(is_target_date_closed(future, now=self.before_cutoff))


class CustomerRequestDateClosureFormTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.zadavatel = User.objects.create_user("cr_close_zad", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.admin = User.objects.create_user("cr_close_admin", password="pw")
        set_user_role(self.admin, ROLE_ADMIN)
        self.today = date(2026, 6, 20)

        settings = AppSettings.load()
        settings.customer_request_daily_cutoff_time = time(12, 0)
        settings.no_service_on_saturday = False
        settings.no_service_on_sunday = False
        settings.save(
            update_fields=[
                "customer_request_daily_cutoff_time",
                "no_service_on_saturday",
                "no_service_on_sunday",
            ]
        )

        self.name = NameCatalog.objects.create(value="Subjekt closure CR")
        NameSubjectProfile.objects.create(
            name=self.name,
            ico=IcoCatalog.objects.create(value="11223300"),
        )
        self.address = AddressCatalog.objects.create(value="Closure ulice, 1, Město")
        self.wt = WasteTypeCatalog.objects.create(code="200311", value="W closure")
        self.suf = SuffixCatalog.objects.create(value="KVc")
        self.vk = VehicleKindCatalog.objects.create(name="Hák cl", shortcut="Hcl", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz closure", visible_for_submitter=True)
        meta = waste_type_combo_metadata()
        self.waste_label = meta[str(self.wt.pk)]["label"]

    def _base_post_data(self, **overrides):
        data = {
            "name_existing": str(self.name.pk),
            "name_lookup": self.name.value,
            "activity": str(self.activity.pk),
            "vehicle_kind": str(self.vk.pk),
            "waste_type": str(self.wt.pk),
            "waste_type_lookup": self.waste_label,
            "suffix": str(self.suf.pk),
            "target_date": self.today.isoformat(),
            "address_value": self.address.value,
            "facility_address_value": "",
            "contact_phone": "",
            "contact_note": "",
            "note": "",
            "has_follow_up": "",
            "follow_up_activity": "",
            "follow_up_target_date": "",
            "is_recurring": "",
            "requires_advance_invoice": "",
        }
        data.update(overrides)
        return data

    @patch("waste_docs.services.customer_request_date_closure.timezone.localtime")
    def test_form_blocks_today_after_cutoff(self, mock_localtime):
        tz = timezone.get_current_timezone()
        mock_localtime.return_value = timezone.make_aware(datetime(2026, 6, 20, 13, 0), tz)
        form = CustomerRequestForm(
            self._base_post_data(),
            submit_user=self.zadavatel,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("target_date", form.errors)

    @patch("waste_docs.services.customer_request_date_closure.timezone.localtime")
    def test_form_blocks_tomorrow_after_cutoff(self, mock_localtime):
        tz = timezone.get_current_timezone()
        mock_localtime.return_value = timezone.make_aware(datetime(2026, 6, 20, 13, 0), tz)
        form = CustomerRequestForm(
            self._base_post_data(target_date=(self.today + timedelta(days=1)).isoformat()),
            submit_user=self.zadavatel,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("target_date", form.errors)

    @patch("waste_docs.services.customer_request_date_closure.timezone.localtime")
    def test_admin_bypasses_closure(self, mock_localtime):
        tz = timezone.get_current_timezone()
        mock_localtime.return_value = timezone.make_aware(datetime(2026, 6, 20, 13, 0), tz)
        form = CustomerRequestForm(
            self._base_post_data(),
            submit_user=self.admin,
        )
        self.assertTrue(form.is_valid(), msg=form.errors)

    def test_manual_closure_error_message(self):
        User = get_user_model()
        disp = User.objects.create_user("cr_close_msg", password="pw")
        set_user_role(disp, ROLE_DISPECER)
        tz = timezone.get_current_timezone()
        before = timezone.make_aware(datetime(2026, 6, 20, 8, 0), tz)
        future = self.today + timedelta(days=10)
        toggle_manual_closure(disp, future, now=before)
        err = target_date_closure_error(future, user=self.zadavatel, now=before)
        self.assertIn("dispečerem", err or "")

    @patch("waste_docs.services.customer_request_date_closure.timezone.localtime")
    def test_post_create_blocked_after_cutoff(self, mock_localtime):
        tz = timezone.get_current_timezone()
        mock_localtime.return_value = timezone.make_aware(datetime(2026, 6, 20, 13, 0), tz)
        client = Client()
        client.force_login(self.zadavatel)
        response = client.post(reverse("waste_docs:customer_request_create"), self._base_post_data())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CustomerRequest.objects.filter(name=self.name).count(), 0)

    @patch("waste_docs.services.customer_request_date_closure.timezone.localtime")
    def test_form_allows_manually_reopened_day(self, mock_localtime):
        User = get_user_model()
        disp = User.objects.create_user("cr_close_form_reopen", password="pw")
        set_user_role(disp, ROLE_DISPECER)
        tz = timezone.get_current_timezone()
        after_cutoff = timezone.make_aware(datetime(2026, 6, 20, 13, 0), tz)
        mock_localtime.return_value = after_cutoff
        tomorrow = self.today + timedelta(days=1)
        toggle_manual_closure(disp, tomorrow, now=after_cutoff)
        form = CustomerRequestForm(
            self._base_post_data(target_date=tomorrow.isoformat()),
            submit_user=self.zadavatel,
        )
        self.assertTrue(form.is_valid(), msg=form.errors)

    @patch("waste_docs.services.customer_request_date_closure.timezone.localtime")
    def test_post_create_succeeds_after_manual_reopen(self, mock_localtime):
        User = get_user_model()
        disp = User.objects.create_user("cr_close_post_reopen", password="pw")
        set_user_role(disp, ROLE_DISPECER)
        tz = timezone.get_current_timezone()
        after_cutoff = timezone.make_aware(datetime(2026, 6, 20, 13, 0), tz)
        mock_localtime.return_value = after_cutoff
        tomorrow = self.today + timedelta(days=1)
        toggle_manual_closure(disp, tomorrow, now=after_cutoff)
        client = Client()
        client.force_login(self.zadavatel)
        response = client.post(
            reverse("waste_docs:customer_request_create"),
            self._base_post_data(target_date=tomorrow.isoformat()),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CustomerRequest.objects.filter(name=self.name, target_date=tomorrow).count(), 1)


class FarFutureDashboardRefreshTests(TestCase):
    """Vzdálené dny nesmí dostat setTimeout (přetečení ~24,8 dne v prohlížeči)."""

    @patch(
        "waste_docs.services.customer_request_date_closure.auto_cutoff_time",
        return_value=time(13, 0),
    )
    def test_no_refresh_token_for_november_from_august(self, _cutoff):
        now = timezone.make_aware(datetime(2026, 8, 18, 11, 0), timezone.get_current_timezone())
        ctx = dashboard_closure_context(date(2026, 11, 11), now=now)
        self.assertFalse(ctx.is_closed)
        self.assertIsNone(ctx.auto_ui_refresh_at)

    @patch(
        "waste_docs.services.customer_request_date_closure.auto_cutoff_time",
        return_value=time(13, 0),
    )
    def test_no_refresh_token_for_day_beyond_timeout_limit(self, _cutoff):
        now = timezone.make_aware(datetime(2026, 8, 18, 11, 0), timezone.get_current_timezone())
        ctx = dashboard_closure_context(date(2026, 9, 13), now=now)
        self.assertFalse(ctx.is_closed)
        self.assertIsNone(ctx.auto_ui_refresh_at)

    @patch(
        "waste_docs.services.customer_request_date_closure.auto_cutoff_time",
        return_value=time(13, 0),
    )
    def test_refresh_still_scheduled_when_cutoff_is_soon(self, _cutoff):
        now = timezone.make_aware(datetime(2026, 8, 18, 11, 0), timezone.get_current_timezone())
        tomorrow = date(2026, 8, 19)
        ctx = dashboard_closure_context(tomorrow, now=now)
        self.assertFalse(ctx.is_closed)
        self.assertIsNotNone(ctx.auto_ui_refresh_at)


class CustomerRequestDateClosureDashboardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.dispecer = User.objects.create_user("cr_close_dash", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.zadavatel = User.objects.create_user("cr_close_dash_z", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.day = date(2026, 8, 10)

        settings = AppSettings.load()
        settings.customer_request_daily_cutoff_time = time(12, 0)
        settings.no_service_on_saturday = False
        settings.no_service_on_sunday = False
        settings.save(
            update_fields=[
                "customer_request_daily_cutoff_time",
                "no_service_on_saturday",
                "no_service_on_sunday",
            ]
        )
        tz = timezone.get_current_timezone()
        self.after_cutoff = timezone.make_aware(datetime(2026, 8, 9, 13, 0), tz)
        self.tomorrow = self.day

    def test_dispatcher_can_toggle_closure_from_dashboard(self):
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:customer_request_closure_toggle")
        response = client.post(url, {"date": self.day.isoformat()})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CustomerRequestDateClosure.objects.filter(closure_date=self.day, is_closed=True).exists()
        )
        response = client.post(url, {"date": self.day.isoformat()})
        self.assertEqual(response.status_code, 302)
        row = CustomerRequestDateClosure.objects.get(closure_date=self.day)
        self.assertFalse(row.is_closed)

    def test_zadavatel_cannot_toggle_closure(self):
        client = Client()
        client.force_login(self.zadavatel)
        url = reverse("waste_docs:customer_request_closure_toggle")
        response = client.post(url, {"date": self.day.isoformat()})
        self.assertEqual(response.status_code, 404)

    def test_dashboard_shows_toggle_for_dispatcher(self):
        client = Client()
        client.force_login(self.dispecer)
        response = client.get(reverse("core:dashboard") + f"?date={self.day.isoformat()}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Požadavky: uzavřít")

    def test_dashboard_shows_readonly_status_for_zadavatel(self):
        client = Client()
        client.force_login(self.zadavatel)
        response = client.get(reverse("core:dashboard") + f"?date={self.day.isoformat()}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Požadavky otevřeny (10. 8.)")
        self.assertNotContains(response, "Požadavky: uzavřít")

    @patch("waste_docs.services.customer_request_date_closure.timezone.localtime")
    def test_zadavatel_dashboard_shows_open_after_manual_reopen(self, mock_localtime):
        mock_localtime.return_value = self.after_cutoff
        self.assertTrue(is_target_date_closed(self.tomorrow, now=self.after_cutoff))
        toggle_manual_closure(self.dispecer, self.tomorrow, now=self.after_cutoff)
        client = Client()
        client.force_login(self.zadavatel)
        response = client.get(reverse("core:dashboard") + f"?date={self.tomorrow.isoformat()}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Požadavky otevřeny (10. 8.)")
        self.assertNotContains(response, "Požadavky uzavřeny")

    def test_far_future_dashboard_renders_panels(self):
        client = Client()
        client.force_login(self.dispecer)
        for day in (date(2026, 9, 13), date(2026, 11, 11)):
            with self.subTest(day=day.isoformat()):
                response = client.get(reverse("core:dashboard"), {"date": day.isoformat()})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "dash-board__body-cols")
                self.assertContains(response, "dash-panel--drivers")
