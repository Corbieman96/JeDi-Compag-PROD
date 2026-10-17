"""Po uložení plánu se otevřené požadavky srovnají s aktuálními sloty řidičů."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    DriverProfile,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile

from waste_docs.models import SvozTask, SvozYardDriverPlan
from waste_docs.services.svoz_dispatch import reconcile_open_tasks_with_plan_for_plan_date
from waste_docs.services.svoz_dispatch.plan import replace_yard_driver_plan_for_date


class SvozPlanReconcileTests(TestCase):
    def setUp(self):
        self.day = date(2032, 6, 10)
        User = get_user_model()
        self.actor = User.objects.create_user("reconcile_user", password="pw")
        name = NameCatalog.objects.create(value="Reconcile yard")
        self.subject = NameSubjectProfile.objects.create(name=name, company_name="SD Reconcile")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()
        self.wt = WasteTypeCatalog.objects.create(code="REC01", value="W")
        self.suf = SuffixCatalog.objects.create(value="KV")
        self.vk = VehicleKindCatalog.objects.create(name="VK REC", shortcut="RC", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz REC")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=True,
        )
        self.old_driver = DriverProfile.objects.create(personal_number="REC-OLD", last_name="Mrňavý")
        self.new_driver = DriverProfile.objects.create(personal_number="REC-NEW", last_name="Nový")
        self.old_rz = VehicleRzCatalog.objects.create(value="REOLD")
        self.new_rz = VehicleRzCatalog.objects.create(value="RENEW")
        for rz, drv in ((self.old_rz, self.old_driver), (self.new_rz, self.new_driver)):
            prof = VehicleRzProfile.objects.create(rz=rz)
            prof.vehicle_kinds.add(self.vk)

        self.task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="C-1",
            target_date=self.day,
            assigned_driver=self.old_driver,
            assigned_vehicle_rz=self.old_rz,
        )

    def _save_plan_with_driver(self, driver, rz, *, sort_order=0):
        replace_yard_driver_plan_for_date(
            plan_date=self.day,
            standard_rows=[
                (self.subject.pk, self.vk.pk, [(driver.pk, rz.pk, "", 1)]),
            ],
        )

    def test_reconcile_reassigns_when_driver_removed_from_plan(self):
        self._save_plan_with_driver(self.new_driver, self.new_rz)
        n = reconcile_open_tasks_with_plan_for_plan_date(self.day, actor=self.actor)
        self.assertEqual(n, 1)
        self.task.refresh_from_db()
        self.assertEqual(self.task.assigned_driver_id, self.new_driver.pk)
        self.assertEqual(self.task.assigned_vehicle_rz_id, self.new_rz.pk)

    def test_reconcile_clears_assignment_when_plan_has_no_drivers(self):
        SvozYardDriverPlan.objects.filter(plan_date=self.day).delete()
        n = reconcile_open_tasks_with_plan_for_plan_date(self.day, actor=self.actor)
        self.assertEqual(n, 1)
        self.task.refresh_from_db()
        self.assertIsNone(self.task.assigned_driver_id)
        self.assertIsNone(self.task.assigned_vehicle_rz_id)

    def test_reconcile_skips_task_already_matching_plan(self):
        self._save_plan_with_driver(self.old_driver, self.old_rz)
        n = reconcile_open_tasks_with_plan_for_plan_date(self.day, actor=self.actor)
        self.assertEqual(n, 0)
        self.task.refresh_from_db()
        self.assertEqual(self.task.assigned_driver_id, self.old_driver.pk)
