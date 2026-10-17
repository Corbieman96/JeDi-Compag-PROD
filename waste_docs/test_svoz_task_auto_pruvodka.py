"""Automatické založení průvodky ze SvozTask (plán RZ vs. filtrování PruvodkaForm)."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    ContainerPassport,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.activity_field_rule import ActivityFieldKey, ActivityFieldMode, ActivityFieldRule
from catalogs.models.vehicle_rz import VehicleKindCatalog, VehicleRzProfile

from waste_docs.models import Pruvodka, SvozTask, SvozYardDriverPlan
from waste_docs.services.svoz_dispatch import assign_driver_for_new_task
from waste_docs.services.svoz_dispatch.assignment import (
    auto_create_rides_for_assigned_tasks_on_date,
    backfill_open_tasks_for_plan_date,
)
from waste_docs.services.svoz_task_auto_pruvodka import try_create_pruvodka_for_assigned_svoz_task


class SvozTaskAutoPruvodkaTests(TestCase):
    """RZ ze slotu plánu může mít DRUH vk, aniž má být activity navázána na vk v číselníku — union querysetu nesmí chybět."""

    def setUp(self):
        self.day = date(2035, 2, 1)
        User = get_user_model()
        self.actor = User.objects.create_user("auto_pr_auto", password="pw", is_superuser=True)

        self.name = NameCatalog.objects.create(value="Sub auto pr")
        self.ico = IcoCatalog.objects.create(value="12345679")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            company_name="Auto pr yard",
            ico=self.ico,
        )
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()
        adr = AddressCatalog.objects.create(value="Náměstí, 12, město XYZ")
        ap = self.subject.address_profile
        ap.fulfillment_address = adr
        ap.save()

        self.wt = WasteTypeCatalog.objects.create(code="200399", value="W auto pr")
        self.suf = SuffixCatalog.objects.create(value="AP")
        self.vk = VehicleKindCatalog.objects.create(name="Vk auto pr", shortcut="Va", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svc auto pr rozpad")
        self.activity.require_nitropodnikovy_subjekt = False
        self.activity.save()
        self.activity.vehicle_kinds.clear()
        ActivityFieldRule.objects.create(
            activity=self.activity,
            field_key=ActivityFieldKey.CONTAINER_1,
            mode=ActivityFieldMode.OFF,
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

        self.rz = VehicleRzCatalog.objects.create(value="RZAUTORZ")
        self.prof = VehicleRzProfile.objects.create(rz=self.rz)
        self.prof.vehicle_kinds.add(self.vk)

        self.driver = DriverProfile.objects.create(personal_number="APR-D1", last_name="Aut")

        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=True,
        )

    def _ensure_plan(self, *, vehicle_rz=None):
        rz = vehicle_rz if vehicle_rz is not None else self.rz
        SvozYardDriverPlan.objects.get_or_create(
            plan_date=self.day,
            subject_profile=self.subject,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
            defaults={
                "driver": self.driver,
                "vehicle_rz": rz,
            },
        )

    def test_try_create_ok_when_vehicle_rz_not_in_strict_activity_linked_queryset(self):
        """Činnost v číselníku nemá VK v vehicle_kinds; RZ profil jen VK → dříve by ModelChoice odmítnul hodnotu ze plánu."""
        self._ensure_plan()
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="",
            target_date=self.day,
            assigned_driver=self.driver,
            assigned_vehicle_rz=self.rz,
        )
        ok, err = try_create_pruvodka_for_assigned_svoz_task(task, self.actor)
        self.assertTrue(ok, msg=err or "")
        self.assertIsNone(err)
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.DONE)
        self.assertIsNotNone(task.resolved_pruvodka_id)

    def test_try_create_blocked_when_profile_disallows_create(self):
        from users.constants import ROLE_DISPECER
        from users.services.access_profile import get_access_profile
        from users.services.roles import set_user_role

        User = get_user_model()
        disp = User.objects.create_user("auto_pr_disp", password="pw")
        set_user_role(disp, ROLE_DISPECER)
        prof = get_access_profile(disp)
        prof.can_create_pruvodka = False
        prof.save(update_fields=["can_create_pruvodka"])

        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=disp,
            waste_type=self.wt,
            suffix=self.suf,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="",
            target_date=self.day,
            assigned_driver=self.driver,
            assigned_vehicle_rz=self.rz,
        )
        ok, err = try_create_pruvodka_for_assigned_svoz_task(task, disp)
        self.assertFalse(ok)
        self.assertIsNone(err)
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.OPEN)
        self.assertIsNone(task.resolved_pruvodka_id)

    def test_backfill_fills_vehicle_rz_from_plan_then_creates_ride(self):
        """Úkol se řidičem ale bez RZ: po doplnění RZ ve slotu plánu zpětným uložením se RZ propsá a zakládá jízda."""
        self._ensure_plan()
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="",
            target_date=self.day,
            assigned_driver=self.driver,
            assigned_vehicle_rz=None,
        )
        n, errs = backfill_open_tasks_for_plan_date(self.day, actor=self.actor)
        self.assertFalse(errs, msg=str(errs))
        self.assertGreaterEqual(n, 1)
        task.refresh_from_db()
        self.assertEqual(task.assigned_vehicle_rz_id, self.rz.pk)
        self.assertEqual(task.status, SvozTask.Status.DONE)

    def test_auto_create_skips_tasks_without_assigned_vehicle_rz(self):
        """Bez řádků v plánu nejde RZ doplnit — auto_create z požadavků jen s řidičem nic nevytvoří."""
        self._ensure_plan(vehicle_rz=None)
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="",
            target_date=self.day,
            assigned_driver=self.driver,
            assigned_vehicle_rz=None,
        )
        created, errs = auto_create_rides_for_assigned_tasks_on_date(self.day, actor=self.actor)
        self.assertFalse(errs, msg=str(errs))
        self.assertEqual(created, 0)
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.OPEN)

    def test_try_create_with_required_container_before_passport_exists_in_catalog(self):
        """Činnost vyžaduje kontejner (1); číslo ze svozu není v číselníku — stub musí vzniknout před validací formuláře."""
        ActivityFieldRule.objects.filter(
            activity=self.activity,
            field_key=ActivityFieldKey.CONTAINER_1,
        ).delete()
        ActivityFieldRule.objects.create(
            activity=self.activity,
            field_key=ActivityFieldKey.CONTAINER_1,
            mode=ActivityFieldMode.REQUIRED,
        )
        cid = "614"
        self.assertFalse(ContainerPassport.objects.filter(container_number__iexact=cid).exists())
        self._ensure_plan()
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers=cid,
            target_date=self.day,
            assigned_driver=self.driver,
            assigned_vehicle_rz=self.rz,
        )
        ok, err = try_create_pruvodka_for_assigned_svoz_task(task, self.actor)
        self.assertTrue(ok, msg=err or "")
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.DONE)
        self.assertTrue(ContainerPassport.objects.filter(container_number__iexact=cid).exists())

    def test_container_passport_stub_linked_after_try_create_with_container_number(self):
        cid = "CP-AUTO-STUB-01"
        self._ensure_plan()
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers=cid,
            target_date=self.day,
            assigned_driver=self.driver,
            assigned_vehicle_rz=self.rz,
        )
        ok, err = try_create_pruvodka_for_assigned_svoz_task(task, self.actor)
        self.assertTrue(ok, msg=err or "")
        task.refresh_from_db()
        pruv = task.resolved_pruvodka
        self.assertIsNotNone(pruv.container_passport_id)
        passport = ContainerPassport.objects.filter(pk=pruv.container_passport_id).first()
        self.assertIsNotNone(passport)
        self.assertEqual(passport.container_number.strip().upper(), cid.strip().upper())
        self.assertEqual(passport.vehicle_kind_id, self.vk.pk)

    def test_assign_driver_returns_error_message_when_try_create_validation_fails(self):
        self._ensure_plan()
        self.subject.address_profile.fulfillment_address = None
        self.subject.address_profile.save(update_fields=["fulfillment_address_id"])

        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="",
            target_date=self.day,
        )
        msg = assign_driver_for_new_task(task, self.pair, actor=self.actor)
        task.refresh_from_db()
        self.assertIsNotNone(msg)
        self.assertEqual(task.status, SvozTask.Status.OPEN)

    def test_try_create_skips_when_existing_ride_same_container(self):
        """Existující jízda stejného kontejneru na cílový den blokuje druhou auto-průvodku."""
        self._ensure_plan()
        cid = "614-DUP-SKIP"
        Pruvodka.objects.create(
            name=self.name,
            ico=self.ico,
            address=self.subject.address_profile.fulfillment_address,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="WC614DUP"),
            waste_category=WasteCategoryCatalog.objects.create(value="KC614DUP"),
            suffix=self.suf,
            activity=self.activity,
            drive_date=self.day,
            container_number=cid,
            created_by=self.actor,
        )
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers=cid,
            target_date=self.day,
            assigned_driver=self.driver,
            assigned_vehicle_rz=self.rz,
        )
        ok, err = try_create_pruvodka_for_assigned_svoz_task(task, self.actor)
        self.assertFalse(ok)
        self.assertIsNone(err)
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.OPEN)
        self.assertIsNone(task.resolved_pruvodka_id)

    def test_try_create_silent_skip_when_no_plan_for_target_date(self):
        SvozYardDriverPlan.objects.filter(plan_date=self.day, subject_profile=self.subject).delete()
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="",
            target_date=self.day,
            assigned_driver=self.driver,
            assigned_vehicle_rz=self.rz,
        )
        ok, err = try_create_pruvodka_for_assigned_svoz_task(task, self.actor)
        self.assertFalse(ok)
        self.assertIsNone(err)
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.OPEN)

    def test_try_create_ok_with_plan_and_no_duplicate(self):
        self._ensure_plan()
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="PLAN-OK-01",
            target_date=self.day,
            assigned_driver=self.driver,
            assigned_vehicle_rz=self.rz,
        )
        ok, err = try_create_pruvodka_for_assigned_svoz_task(task, self.actor)
        self.assertTrue(ok, msg=err or "")
        self.assertIsNone(err)
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.DONE)
        self.assertIsNotNone(task.resolved_pruvodka_id)

