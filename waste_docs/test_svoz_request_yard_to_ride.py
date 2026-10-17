"""E2E: matice sběrného dvora → přiřazení z plánu výjimek (V-slot) → automatická průvodka."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
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
from catalogs.models.activity_field_rule import ActivityFieldKey, ActivityFieldMode, ActivityFieldRule
from catalogs.models.vehicle_rz import VehicleRzProfile

from waste_docs.models import Pruvodka, SvozTask, SvozYardDriverPlan
from waste_docs.services.svoz_dispatch import (
    assign_driver_for_new_task,
    backfill_open_tasks_for_plan_date,
)


class SvozRequestYardToRideTests(TestCase):
    def setUp(self):
        self.day = date(2026, 5, 19)
        User = get_user_model()
        self.actor = User.objects.create_user("yard_e2e", password="pw", is_superuser=True)

        self.name = NameCatalog.objects.create(value="Mnichovo E2E")
        self.ico = IcoCatalog.objects.create(value="47551984")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            company_name="SD Mnichovo E2E",
            ico=self.ico,
        )
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()
        adr = AddressCatalog.objects.create(value="Náměstí Míru, 295, Mnichovo Hradiště")
        ap = self.subject.address_profile
        ap.fulfillment_address = adr
        ap.save()

        self.wt = WasteTypeCatalog.objects.create(code="200110", value="Textil E2E")
        self.suf = SuffixCatalog.objects.create(value="KV")
        self.vk = VehicleKindCatalog.objects.create(name="Řetěz E2E", shortcut="R", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz textil E2E")
        self.activity.require_nitropodnikovy_subjekt = False
        self.activity.save()
        ActivityFieldRule.objects.create(
            activity=self.activity,
            field_key=ActivityFieldKey.CONTAINER_1,
            mode=ActivityFieldMode.REQUIRED,
        )
        ActivityFieldRule.objects.create(
            activity=self.activity,
            field_key=ActivityFieldKey.SND_CISLO,
            mode=ActivityFieldMode.OFF,
        )
        ActivityFieldRule.objects.create(
            activity=self.activity,
            field_key=ActivityFieldKey.ZPO,
            mode=ActivityFieldMode.OFF,
        )

        self.driver_b = DriverProfile.objects.create(
            personal_number="69",
            last_name="Běžný",
            first_name="Pavel",
        )
        self.driver_v = DriverProfile.objects.create(
            personal_number="70",
            last_name="Výjimka",
            first_name="Jan",
        )
        self.rz_b = VehicleRzCatalog.objects.create(value="5S19968")
        self.rz_v = VehicleRzCatalog.objects.create(value="5S19969")
        prof_b = VehicleRzProfile.objects.create(rz=self.rz_b)
        prof_b.vehicle_kinds.add(self.vk)
        prof_v = VehicleRzProfile.objects.create(rz=self.rz_v)
        prof_v.vehicle_kinds.add(self.vk)

        SvozYardDriverPlan.objects.create(
            plan_date=self.day,
            subject_profile=self.subject,
            driver=self.driver_b,
            vehicle_rz=self.rz_b,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
        )

        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=False,
            yard_svoz_exception_slot=1,
        )

    def _task(self, **kwargs):
        defaults = dict(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="614",
            matrix_display_label="[R] Textil — 614",
            target_date=self.day,
        )
        defaults.update(kwargs)
        return SvozTask.objects.create(**defaults)

    def test_exception_with_v_slot_plan_creates_pruvodka(self):
        """Výjimka + kontejner + řidič/RZ ve V1 → průvodka na tohoto řidiče."""
        SvozYardDriverPlan.objects.create(
            plan_date=self.day,
            subject_profile=self.subject,
            driver=self.driver_v,
            vehicle_rz=self.rz_v,
            row_kind=SvozYardDriverPlan.RowKind.EXCEPTION,
            vehicle_kind=self.vk,
            sort_order=0,
        )
        task = self._task()
        err = assign_driver_for_new_task(task, self.pair, actor=self.actor)
        self.assertIsNone(err, msg=err or "")
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.DONE)
        self.assertEqual(task.assigned_driver_id, self.driver_v.pk)
        self.assertEqual(task.assigned_vehicle_rz_id, self.rz_v.pk)
        self.assertIsNotNone(task.resolved_pruvodka_id)
        pruv = Pruvodka.objects.get(pk=task.resolved_pruvodka_id)
        self.assertEqual(pruv.drive_date, self.day)
        self.assertEqual(pruv.driver_id, self.driver_v.pk)
        self.assertEqual(pruv.vehicle_rz_id, self.rz_v.pk)

    def test_exception_without_v_slot_stays_open_on_dashboard(self):
        """Jen běžný plán B — výjimka se slotem V1 nepoužije fallback, úkol zůstane otevřený."""
        task = self._task()
        err = assign_driver_for_new_task(task, self.pair, actor=self.actor)
        self.assertIsNone(err)
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.OPEN)
        self.assertIsNone(task.assigned_driver_id)
        self.assertIsNone(task.resolved_pruvodka_id)

    def test_exception_without_slot_still_fallbacks_to_standard_plan(self):
        """Výjimka bez slotu V v číselníku — zpětná kompatibilita: fallback na běžný svoz."""
        self.pair.yard_svoz_exception_slot = None
        self.pair.save(update_fields=["yard_svoz_exception_slot"])
        task = self._task()
        err = assign_driver_for_new_task(task, self.pair, actor=self.actor)
        self.assertIsNone(err, msg=err or "")
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.DONE)
        self.assertEqual(task.assigned_driver_id, self.driver_b.pk)
        self.assertEqual(task.assigned_vehicle_rz_id, self.rz_b.pk)

    def test_backfill_after_plan_save_creates_pruvodka_for_exception(self):
        """Dvůr odešle dřív, dispečer doplní V-slot v plánu — po backfillu vznikne průvodka."""
        task = self._task()
        assign_driver_for_new_task(task, self.pair, actor=self.actor)
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.OPEN)

        SvozYardDriverPlan.objects.create(
            plan_date=self.day,
            subject_profile=self.subject,
            driver=self.driver_v,
            vehicle_rz=self.rz_v,
            row_kind=SvozYardDriverPlan.RowKind.EXCEPTION,
            vehicle_kind=self.vk,
            sort_order=0,
        )
        updated, _errs = backfill_open_tasks_for_plan_date(self.day, actor=self.actor)
        self.assertGreaterEqual(updated, 1)
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.DONE)
        self.assertEqual(task.assigned_driver_id, self.driver_v.pk)
        self.assertIsNotNone(task.resolved_pruvodka_id)

    def test_exception_v2_task_uses_v1_plan_when_own_slot_empty(self):
        """Plán jen na V1 — úkol na výjimkovém řádku V2 dostane řidiče z V1 a průvodku."""
        pair_v2 = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=False,
            yard_svoz_exception_slot=2,
            yard_svoz_display_label="Textil E2E",
        )
        SvozYardDriverPlan.objects.create(
            plan_date=self.day,
            subject_profile=self.subject,
            driver=self.driver_v,
            vehicle_rz=self.rz_v,
            row_kind=SvozYardDriverPlan.RowKind.EXCEPTION,
            vehicle_kind=self.vk,
            sort_order=0,
        )
        task = self._task(
            source_waste_suffix_pair=pair_v2,
            container_numbers="247",
            matrix_display_label="Textil E2E: 247",
        )
        err = assign_driver_for_new_task(task, pair_v2, actor=self.actor)
        self.assertIsNone(err, msg=err or "")
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.DONE)
        self.assertEqual(task.assigned_driver_id, self.driver_v.pk)
        self.assertEqual(task.assigned_vehicle_rz_id, self.rz_v.pk)
        self.assertIsNotNone(task.resolved_pruvodka_id)

    def test_exception_v2_backfill_uses_v1_plan_when_own_slot_empty(self):
        """Po uložení plánu jen na V1 backfill uzavře úkol na řádku matice V2."""
        pair_v2 = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=False,
            yard_svoz_exception_slot=2,
        )
        task = self._task(
            source_waste_suffix_pair=pair_v2,
            container_numbers="248",
        )
        assign_driver_for_new_task(task, pair_v2, actor=self.actor)
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.OPEN)

        SvozYardDriverPlan.objects.create(
            plan_date=self.day,
            subject_profile=self.subject,
            driver=self.driver_v,
            vehicle_rz=self.rz_v,
            row_kind=SvozYardDriverPlan.RowKind.EXCEPTION,
            vehicle_kind=self.vk,
            sort_order=0,
        )
        updated, errs = backfill_open_tasks_for_plan_date(self.day, actor=self.actor)
        self.assertGreaterEqual(updated, 1, msg=errs)
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.DONE)
        self.assertEqual(task.assigned_driver_id, self.driver_v.pk)
        self.assertIsNotNone(task.resolved_pruvodka_id)
