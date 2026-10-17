"""Svoz-plan: v selectu řidičů jen ti z dashboard panelu Řidiči (bez Nepřítomnosti)."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    DriverAbsence,
    DriverProfile,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    WasteTypeCatalog,
)
from catalogs.services.driver_absence import driver_ids_hidden_from_drivers_panel


class SvozPlanHideAbsentDriversTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("svoz_abs_admin", password="pw", is_superuser=True)
        self.client = Client()
        self.client.force_login(self.admin)
        self.plan_date = date(2033, 3, 15)

        nm = NameCatalog.objects.create(value="Svoz abs yard")
        self.subject = NameSubjectProfile.objects.create(name=nm, company_name="Svoz abs dvůr")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()

        self.vk = VehicleKindCatalog.objects.create(name="Vk abs", shortcut="VA", sort_order=0)
        wt = WasteTypeCatalog.objects.create(code="200501", value="W abs")
        sfx = SuffixCatalog.objects.create(value="SFXABS")
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=wt,
            suffix=sfx,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_auto_assign_driver=True,
        )

        self.ok = DriverProfile.objects.create(personal_number="ABS-OK", last_name="Ok")
        self.vacation = DriverProfile.objects.create(personal_number="ABS-VAC", last_name="Dovolena")
        self.other = DriverProfile.objects.create(personal_number="ABS-OTH", last_name="Jiny")
        for d in (self.ok, self.vacation, self.other):
            d.allowed_vehicle_kinds.add(self.vk)

        DriverAbsence.objects.create(
            driver=self.vacation,
            absence_type=DriverAbsence.AbsenceType.VACATION,
            date_from=self.plan_date,
            date_to=self.plan_date,
            is_partial=False,
        )
        DriverAbsence.objects.create(
            driver=self.other,
            absence_type=DriverAbsence.AbsenceType.OTHER,
            date_from=self.plan_date,
            date_to=self.plan_date,
            is_partial=False,
            note="Školení",
        )

    def test_helper_matches_dashboard_strip_rules(self):
        hidden = driver_ids_hidden_from_drivers_panel(self.plan_date)
        self.assertIn(self.vacation.pk, hidden)
        self.assertNotIn(self.other.pk, hidden)
        self.assertNotIn(self.ok.pk, hidden)

    def test_svoz_plan_driver_select_hides_vacation_keeps_other(self):
        response = self.client.get(
            f"{reverse('waste_docs:svoz_dispatch_plan')}?date={self.plan_date.isoformat()}"
        )
        self.assertEqual(response.status_code, 200)
        driver_ids: set[int] = set()
        for block in response.context["yard_blocks"]:
            for section in block["kind_sections"]:
                driver_ids.update(d.pk for d in section["drivers"])
            for group in block.get("exception_groups") or []:
                for ep in group.get("pairs") or []:
                    driver_ids.update(d.pk for d in ep["drivers"])

        self.assertIn(self.ok.pk, driver_ids)
        self.assertIn(self.other.pk, driver_ids)
        self.assertNotIn(self.vacation.pk, driver_ids)
