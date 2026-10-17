"""Test množin RZ pro nápovědy na plánu svozů (průvodka / duplicitní sloty)."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogs.models import (
    AddressCatalog,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleKindCatalog

from waste_docs.models import Pruvodka, SvozYardDriverPlan
from waste_docs.services.svoz_dispatch.plan_vehicle_rz_day_hints import (
    vehicle_rz_ids_multi_assigned_in_plan,
    vehicle_rz_ids_with_pruvodka_on_date,
)


class PlanVehicleRzDayHintsTests(TestCase):
    def setUp(self):
        self.plan_date = date(2032, 4, 6)
        User = get_user_model()
        self.admin = User.objects.create_user("hints_admin", password="pw", is_superuser=True)
        self.other = User.objects.create_user("hints_other", password="pw")

        nm = NameCatalog.objects.create(value="Nm hints")
        self.subject = NameSubjectProfile.objects.create(name=nm, company_name="Hints yard")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()

        self.rz1 = VehicleRzCatalog.objects.create(value="RZHNTS1")
        self.rz2 = VehicleRzCatalog.objects.create(value="RZHNTS2")
        self.vk = VehicleKindCatalog.objects.create(name="Vk hints", shortcut="VH", sort_order=0)
        DriverProfile.objects.create(personal_number="HN-DRV", last_name="X")
        DriverProfile.objects.create(personal_number="HN-DRV2", last_name="Y")

    def test_multi_assigned_collects_duplicate_rz_in_plan_rows(self):
        SvozYardDriverPlan.objects.create(
            plan_date=self.plan_date,
            subject_profile=self.subject,
            driver=self._driver_a(),
            vehicle_rz=self.rz1,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
        )
        SvozYardDriverPlan.objects.create(
            plan_date=self.plan_date,
            subject_profile=self.subject,
            driver=self._driver_b(),
            vehicle_rz=self.rz1,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=1,
        )
        self.assertEqual(vehicle_rz_ids_multi_assigned_in_plan(self.plan_date), frozenset({self.rz1.pk}))

    def test_multi_assigned_ignores_single_use_rz(self):
        SvozYardDriverPlan.objects.create(
            plan_date=self.plan_date,
            subject_profile=self.subject,
            driver=self._driver_a(),
            vehicle_rz=self.rz2,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
        )
        self.assertEqual(vehicle_rz_ids_multi_assigned_in_plan(self.plan_date), frozenset())

    def test_pruvodka_ids_dispatcher_sees_other_users_records(self):
        name_for_pruv = NameCatalog.objects.create(value="Nm pruv hints")
        suf = SuffixCatalog.objects.create(value="SUFXHP")
        Pruvodka.objects.create(
            name=name_for_pruv,
            ico=IcoCatalog.objects.create(value="88888888"),
            address=AddressCatalog.objects.create(value="Adr hints 1"),
            waste_type=WasteTypeCatalog.objects.create(code="200304", value="Wh"),
            waste_code=WasteCodeCatalog.objects.create(value="WCXHP"),
            waste_category=WasteCategoryCatalog.objects.create(value="KY"),
            suffix=suf,
            drive_date=self.plan_date,
            vehicle_rz=self.rz1,
            container_number="",
            created_by=self.other,
        )
        ids = vehicle_rz_ids_with_pruvodka_on_date(self.plan_date, user=self.admin)
        self.assertEqual(ids, frozenset({self.rz1.pk}))

    def test_pruvodka_ids_non_dispatcher_only_own_when_used(self):
        name_for_pruv = NameCatalog.objects.create(value="Nm pruv hints II")
        suf = SuffixCatalog.objects.create(value="SUFXHR")
        pk_rz = VehicleRzCatalog.objects.create(value="RZOWN1")
        Pruvodka.objects.create(
            name=name_for_pruv,
            ico=IcoCatalog.objects.create(value="77777777"),
            address=AddressCatalog.objects.create(value="Adr hints 2"),
            waste_type=WasteTypeCatalog.objects.create(code="200305", value="Wz"),
            waste_code=WasteCodeCatalog.objects.create(value="WCXHR"),
            waste_category=WasteCategoryCatalog.objects.create(value="KZ"),
            suffix=suf,
            drive_date=self.plan_date,
            vehicle_rz=pk_rz,
            container_number="",
            created_by=self.other,
        )
        ids_own = vehicle_rz_ids_with_pruvodka_on_date(self.plan_date, user=self.other)
        self.assertEqual(ids_own, frozenset({pk_rz.pk}))

    def test_pruvodka_excludes_archived(self):
        name_for_pruv = NameCatalog.objects.create(value="Nm arch hints")
        suf = SuffixCatalog.objects.create(value="SUFARC")
        p = Pruvodka.objects.create(
            name=name_for_pruv,
            ico=IcoCatalog.objects.create(value="66666666"),
            address=AddressCatalog.objects.create(value="Adr hints 3"),
            waste_type=WasteTypeCatalog.objects.create(code="200306", value="Wa"),
            waste_code=WasteCodeCatalog.objects.create(value="WCARC"),
            waste_category=WasteCategoryCatalog.objects.create(value="KW"),
            suffix=suf,
            drive_date=self.plan_date,
            vehicle_rz=self.rz1,
            container_number="",
            created_by=self.admin,
        )
        p.is_archived = True
        p.save(update_fields=["is_archived"])
        self.assertEqual(
            vehicle_rz_ids_with_pruvodka_on_date(self.plan_date, user=self.admin),
            frozenset(),
        )

    def _driver_a(self):
        return DriverProfile.objects.get(personal_number="HN-DRV")

    def _driver_b(self):
        return DriverProfile.objects.get(personal_number="HN-DRV2")
