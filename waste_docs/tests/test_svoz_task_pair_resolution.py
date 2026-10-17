"""Auto-průvodka: správný řádek matice při více druzích vozidel (Hák vs. Řetěz)."""

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
from catalogs.services.name_subject_pair_vehicle_kinds import pair_for_svoz_task_record

from waste_docs.models import SvozTask, SvozYardDriverPlan
from waste_docs.services.svoz_task_auto_pruvodka import try_create_pruvodka_for_assigned_svoz_task


class SvozTaskPairResolutionTests(TestCase):
    """Stejný odpad/suffix, dva řádky matice — auto-create musí použít source_waste_suffix_pair."""

    databases = {"default", "addresses"}

    def setUp(self):
        self.day = date(2036, 6, 12)
        User = get_user_model()
        self.actor = User.objects.create_user("pair_res", password="pw", is_superuser=True)

        self.name = NameCatalog.objects.create(value="Sub Bakov-like")
        self.ico = IcoCatalog.objects.create(value="47551984")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            company_name="SD test",
            ico=self.ico,
        )
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()
        adr = AddressCatalog.objects.create(value="Bakov, 29401")
        ap = self.subject.address_profile
        ap.fulfillment_address = adr
        ap.save()

        self.wt = WasteTypeCatalog.objects.create(code="200307", value="Plasty PR")
        self.suf = SuffixCatalog.objects.create(value="B")
        self.vk_retez = VehicleKindCatalog.objects.create(name="Řetěz", shortcut="R", sort_order=0)
        self.vk_hak = VehicleKindCatalog.objects.create(name="Hák PR", shortcut="H", sort_order=1)

        self.activity = ActivityCatalog.objects.create(name="Svoz PR")
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

        self.rz_retez = VehicleRzCatalog.objects.create(value="8S74311PR")
        self.prof_retez = VehicleRzProfile.objects.create(rz=self.rz_retez)
        self.prof_retez.vehicle_kinds.add(self.vk_retez)

        self.rz_hak = VehicleRzCatalog.objects.create(value="4SJ5360PR")
        self.prof_hak = VehicleRzProfile.objects.create(rz=self.rz_hak)
        self.prof_hak.vehicle_kinds.add(self.vk_hak)

        self.driver_retez = DriverProfile.objects.create(personal_number="69", last_name="Mašek", first_name="Pavel")
        self.driver_hak = DriverProfile.objects.create(personal_number="77", last_name="Mrňavý", first_name="Aleš")

        self.pair_hak = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk_hak,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=True,
        )
        self.pair_retez = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk_retez,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=True,
        )

        ContainerPassport.objects.create(
            container_number="145",
            vehicle_kind=self.vk_retez,
            color="—",
        )

        SvozYardDriverPlan.objects.create(
            plan_date=self.day,
            subject_profile=self.subject,
            driver=self.driver_retez,
            vehicle_rz=self.rz_retez,
            vehicle_kind=self.vk_retez,
            sort_order=0,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
        )

    def test_auto_create_uses_source_pair_not_first_hak_row(self):
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair_retez,
            vehicle_kind=self.vk_retez,
            activity=self.activity,
            container_numbers="145",
            target_date=self.day,
            assigned_driver=self.driver_retez,
            assigned_vehicle_rz=self.rz_retez,
        )
        ok, err = try_create_pruvodka_for_assigned_svoz_task(task, self.actor)
        self.assertTrue(ok, msg=err)
        task.refresh_from_db()
        self.assertEqual(task.status, SvozTask.Status.DONE)
        self.assertIsNotNone(task.resolved_pruvodka_id)
        self.assertEqual(task.resolved_pruvodka.vehicle_rz_id, self.rz_retez.pk)

    def test_fallback_matches_retez_alias_without_source_pair(self):
        """Starý úkol bez source_pair: Retez vs Řetěz v číselníku — správný řádek matice."""
        vk_retez_ascii = VehicleKindCatalog.objects.create(name="Retez", shortcut="Ra", sort_order=2)
        ContainerPassport.objects.create(
            container_number="145b",
            vehicle_kind=vk_retez_ascii,
            color="—",
        )
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            vehicle_kind=vk_retez_ascii,
            activity=self.activity,
            container_numbers="145b",
            target_date=self.day,
            assigned_driver=self.driver_retez,
            assigned_vehicle_rz=self.rz_retez,
        )
        resolved = pair_for_svoz_task_record(task)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.pk, self.pair_retez.pk)
        self.assertNotEqual(resolved.pk, self.pair_hak.pk)
