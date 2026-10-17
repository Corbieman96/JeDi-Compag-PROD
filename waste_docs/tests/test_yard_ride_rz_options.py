"""Testy nabídky RZ pro nova-jizda."""

from datetime import date

from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile
from waste_docs.models import SvozYardDriverPlan
from waste_docs.services.yard_ride_rz_options import rz_options_for_yard_row


class YardRideRzOptionsTests(TestCase):
    def setUp(self):
        self.plan_date = date(2036, 4, 1)
        self.name = NameCatalog.objects.create(value="RZ yard")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="SD RZ")
        self.wt = WasteTypeCatalog.objects.create(code="200311", value="O RZ")
        self.suf = SuffixCatalog.objects.create(value="KRZ")
        self.vk = VehicleKindCatalog.objects.create(name="Voz RZ", shortcut="R")
        self.activity = ActivityCatalog.objects.create(name="A RZ")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_pruvodka_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_pruvodka_activity=self.activity,
        )
        self.rz_plan = VehicleRzCatalog.objects.create(value="9R99999")
        self.driver = DriverProfile.objects.create(personal_number="RZ-D1", last_name="Plan")
        SvozYardDriverPlan.objects.create(
            plan_date=self.plan_date,
            subject_profile=self.subject,
            driver=self.driver,
            vehicle_rz=self.rz_plan,
            vehicle_kind=self.vk,
            sort_order=0,
        )

    def test_includes_rz_from_plan_without_vehicle_profile(self):
        opts = rz_options_for_yard_row(self.pair, self.subject, self.plan_date)
        pks = {o["pk"] for o in opts}
        self.assertIn(self.rz_plan.pk, pks)

    def test_merges_profile_and_plan_without_duplicates(self):
        rz_prof = VehicleRzCatalog.objects.create(value="8R88888")
        prof = VehicleRzProfile.objects.create(rz=rz_prof)
        prof.vehicle_kinds.add(self.vk)
        opts = rz_options_for_yard_row(self.pair, self.subject, self.plan_date)
        pks = [o["pk"] for o in opts]
        self.assertEqual(len(pks), len(set(pks)))
        self.assertIn(rz_prof.pk, pks)
        self.assertIn(self.rz_plan.pk, pks)
