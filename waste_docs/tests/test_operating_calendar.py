from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

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
from customer_requests.models import CustomerRequest, NoServiceCalendarDay
from users.constants import ROLE_ADMIN, ROLE_ZADAVATEL
from users.services.roles import set_user_role
from waste_docs.forms import CustomerRequestForm
from waste_docs.services.customer_request_recurrence import iter_recurrence_dates
from waste_docs.services.operating_calendar.resolve import (
    is_operating_day,
    resolve_operating_date,
)
from waste_docs.svoz_schedule import next_svoz_target_date


class OperatingCalendarTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.zadavatel = User.objects.create_user("oc_zad", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.admin = User.objects.create_user("oc_admin", password="pw", is_superuser=True)
        set_user_role(self.admin, ROLE_ADMIN)

        settings = AppSettings.load()
        settings.no_service_on_saturday = True
        settings.no_service_on_sunday = True
        settings.customer_request_daily_cutoff_time = None
        settings.save()

        self.sat = date(2026, 9, 26)
        self.holiday = date(2026, 9, 28)
        self.tue = date(2026, 9, 29)
        NoServiceCalendarDay.objects.create(closed_date=self.holiday, note="Svátek")

        self.name = NameCatalog.objects.create(value="Subjekt kalendář")
        NameSubjectProfile.objects.create(
            name=self.name,
            ico=IcoCatalog.objects.create(value="55667788"),
        )
        self.address = AddressCatalog.objects.create(value="Kalendář ulice 1")
        self.wt = WasteTypeCatalog.objects.create(code="200399", value="W kalendář")
        self.suf = SuffixCatalog.objects.create(value="KKal")
        self.vk = VehicleKindCatalog.objects.create(name="Hák kal", shortcut="Hk", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz kalendář", visible_for_submitter=True)
        self.waste_label = waste_type_combo_metadata()[str(self.wt.pk)]["label"]

    def _form_data(self, **overrides):
        data = {
            "name_existing": str(self.name.pk),
            "name_lookup": self.name.value,
            "activity": str(self.activity.pk),
            "vehicle_kind": str(self.vk.pk),
            "waste_type": str(self.wt.pk),
            "waste_type_lookup": self.waste_label,
            "suffix": str(self.suf.pk),
            "target_date": self.sat.isoformat(),
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

    def test_saturday_plus_holiday_resolves_to_tuesday(self):
        self.assertFalse(is_operating_day(self.sat))
        self.assertFalse(is_operating_day(self.holiday))
        self.assertTrue(is_operating_day(self.tue))
        self.assertEqual(resolve_operating_date(self.sat), self.tue)

    def test_holiday_redirect_date(self):
        NoServiceCalendarDay.objects.filter(closed_date=self.holiday).update(
            redirect_date=self.tue
        )
        self.assertEqual(resolve_operating_date(self.holiday), self.tue)

    def test_form_shifts_new_request_to_tuesday(self):
        form = CustomerRequestForm(self._form_data(), submit_user=self.zadavatel)
        self.assertTrue(form.is_valid(), msg=form.errors)
        self.assertEqual(form.cleaned_data["target_date"], self.tue)
        self.assertTrue(form.operating_date_shift_notes)

    def test_admin_keeps_saturday(self):
        form = CustomerRequestForm(self._form_data(), submit_user=self.admin)
        self.assertTrue(form.is_valid(), msg=form.errors)
        self.assertEqual(form.cleaned_data["target_date"], self.sat)
        self.assertEqual(form.operating_date_shift_notes, [])

    def test_post_create_saves_tuesday(self):
        client = Client()
        client.force_login(self.zadavatel)
        response = client.post(reverse("waste_docs:customer_request_create"), self._form_data())
        self.assertEqual(response.status_code, 302)
        cr = CustomerRequest.objects.get(name=self.name)
        self.assertEqual(cr.target_date, self.tue)

    def test_existing_request_is_not_shifted(self):
        cr = CustomerRequest.objects.create(
            created_by=self.zadavatel,
            name=self.name,
            activity=self.activity,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=self.sat,
            status=CustomerRequest.Status.DISPATCHER_REVIEW,
        )
        client = Client()
        client.force_login(self.admin)
        page = client.get(reverse("core:settings"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Dny bez svozu")
        cr.refresh_from_db()
        self.assertEqual(cr.target_date, self.sat)

    def test_yard_matrix_saturday_submit_lands_tuesday(self):
        self.assertEqual(next_svoz_target_date(self.sat), self.tue)

    def test_recurrence_monday_holiday_shifts(self):
        dates = iter_recurrence_dates(self.holiday, date(2026, 10, 5), "0")
        self.assertIn(self.tue, dates)
        self.assertNotIn(self.holiday, dates)

    def test_settings_post_saves_iso_holiday_date(self):
        client = Client()
        client.force_login(self.admin)
        page = client.get(reverse("core:settings"))
        self.assertEqual(page.status_code, 200)
        data = {}
        for name, field in page.context["form"].fields.items():
            value = page.context["form"][name].value()
            if isinstance(value, bool):
                if value:
                    data[name] = "on"
            elif value is not None and value != "":
                data[name] = value.isoformat() if hasattr(value, "isoformat") else str(value)
        formset = page.context["no_service_formset"]
        data["no_service-TOTAL_FORMS"] = str(formset.total_form_count())
        data["no_service-INITIAL_FORMS"] = str(formset.initial_form_count())
        data["no_service-MIN_NUM_FORMS"] = "0"
        data["no_service-MAX_NUM_FORMS"] = "1000"
        extra_index = None
        for i, row in enumerate(formset.forms):
            if row.instance.pk:
                data[f"no_service-{i}-id"] = str(row.instance.pk)
                data[f"no_service-{i}-closed_date"] = row.instance.closed_date.isoformat()
                if row.instance.redirect_date:
                    data[f"no_service-{i}-redirect_date"] = row.instance.redirect_date.isoformat()
                data[f"no_service-{i}-note"] = row.instance.note
            elif extra_index is None:
                extra_index = i
        self.assertIsNotNone(extra_index)
        new_day = date(2026, 12, 24)
        data[f"no_service-{extra_index}-closed_date"] = new_day.isoformat()
        data[f"no_service-{extra_index}-note"] = "Štědrý den"
        response = client.post(reverse("core:settings"), data)
        self.assertEqual(response.status_code, 302, msg=getattr(response, "context", None))
        self.assertTrue(
            NoServiceCalendarDay.objects.filter(closed_date=new_day, note="Štědrý den").exists()
        )
