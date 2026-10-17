"""Auto-průvodka: pasport/RZ sedí při jiném druhu v páru subjektu (H + 3H)."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    ActivityFieldKey,
    ActivityFieldMode,
    ActivityFieldRule,
    AddressCatalog,
    ContainerPassport,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleKindCatalog, VehicleRzProfile
from catalogs.services.vehicle_kind_compatibility import clear_vehicle_kind_compatibility_cache

from waste_docs.models import SvozTask, SvozYardDriverPlan
from waste_docs.services.svoz_dispatch import assign_driver_for_new_task
from waste_docs.services.svoz_task_auto_pruvodka import try_create_pruvodka_for_assigned_svoz_task


class SvozAutoPruvodkaMultiKindTests(TestCase):
    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        self.day = date(2036, 3, 10)
        User = get_user_model()
        self.actor = User.objects.create_user("multi_vk", password="pw", is_superuser=True)

        self.name = NameCatalog.objects.create(value="Sub multi VK")
        self.ico = IcoCatalog.objects.create(value="12345670")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="Y", ico=self.ico)
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()
        adr = AddressCatalog.objects.create(value="Ulice 1, 60200 Brno")
        ap = self.subject.address_profile
        ap.fulfillment_address = adr
        ap.save()

        self.wt = WasteTypeCatalog.objects.create(code="MVK01", value="W")
        self.suf = SuffixCatalog.objects.create(value="S")
        self.vk_h = VehicleKindCatalog.objects.create(name="Hák MK", shortcut="H", sort_order=0)
        self.vk_3h = VehicleKindCatalog.objects.create(
            name="3H MK", shortcut="3H", sort_order=1, parent_kind=self.vk_h
        )
        clear_vehicle_kind_compatibility_cache()

        self.activity = ActivityCatalog.objects.create(name="Act MK")
        self.activity.require_nitropodnikovy_subjekt = False
        self.activity.save()
        ActivityFieldRule.objects.create(
            activity=self.activity, field_key=ActivityFieldKey.CONTAINER_1, mode=ActivityFieldMode.REQUIRED
        )
        ActivityFieldRule.objects.create(
            activity=self.activity, field_key=ActivityFieldKey.SND_CISLO, mode=ActivityFieldMode.OFF
        )
        ActivityFieldRule.objects.create(
            activity=self.activity, field_key=ActivityFieldKey.ZPO, mode=ActivityFieldMode.OFF
        )

        self.rz = VehicleRzCatalog.objects.create(value="RZMK01")
        self.prof = VehicleRzProfile.objects.create(rz=self.rz)
        self.prof.vehicle_kinds.add(self.vk_h)

        self.driver = DriverProfile.objects.create(personal_number="MK-D1", last_name="Drv")

        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=True,
            yard_vehicle_kind=self.vk_h,
        )
        self.pair.yard_vehicle_kinds.set([self.vk_h, self.vk_3h])

        ContainerPassport.objects.create(
            container_number="MK-CONT-1",
            vehicle_kind=self.vk_h,
            color="—",
        )

        SvozYardDriverPlan.objects.create(
            plan_date=self.day,
            subject_profile=self.subject,
            driver=self.driver,
            vehicle_rz=self.rz,
            vehicle_kind=self.vk_3h,
            sort_order=0,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
        )

    def test_auto_pruvodka_task_3h_passport_h_from_pair(self):
        """Úkol/plán 3H, pasport H — projde díky oběma druhům v páru subjektu."""
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            vehicle_kind=self.vk_3h,
            activity=self.activity,
            container_numbers="MK-CONT-1",
            target_date=self.day,
        )
        err = assign_driver_for_new_task(task, self.pair, actor=self.actor)
        self.assertIsNone(err, msg=err)
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.DONE)
        self.assertIsNotNone(task.resolved_pruvodka_id)

    def test_try_create_loops_kinds(self):
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            vehicle_kind=self.vk_3h,
            activity=self.activity,
            container_numbers="MK-CONT-1",
            target_date=self.day,
            assigned_driver=self.driver,
            assigned_vehicle_rz=self.rz,
        )
        ok, err = try_create_pruvodka_for_assigned_svoz_task(task, self.actor)
        self.assertTrue(ok, msg=err)
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.DONE)
