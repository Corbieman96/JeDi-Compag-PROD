"""Směrová kompatibilita druhů vozidel — integrační testy (H / 3H, strom)."""

from django.test import TestCase

from catalogs.models import (
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile
from catalogs.services.name_subject_pair_vehicle_kinds import (
    pair_covering_vehicle_kind_ids,
    pair_vehicle_kind_constraint_hint,
    rz_profile_pair_mismatch_message,
    rz_profile_serves_pair,
)
from catalogs.services.vehicle_kind_compatibility import (
    clear_vehicle_kind_compatibility_cache,
    passport_matches_vehicle_rz_compat,
    rz_profile_serves_task_kind,
    vehicle_kind_covers_task,
)


class DirectionalVehicleKindTests(TestCase):
    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        self.vk_h = VehicleKindCatalog.objects.create(name="Hák dir", shortcut="Hdir", sort_order=101)
        self.vk_3h = VehicleKindCatalog.objects.create(
            name="3H dir", shortcut="3Hdir", sort_order=102, parent_kind=self.vk_h
        )
        self.vk_4h = VehicleKindCatalog.objects.create(
            name="4H dir", shortcut="4Hdir", sort_order=103, parent_kind=self.vk_3h
        )
        clear_vehicle_kind_compatibility_cache()

        self.profile = NameSubjectProfile.objects.create(
            name=NameCatalog.objects.create(value="Subj directional"),
        )
        self.wt1 = WasteTypeCatalog.objects.create(code="DIR01", value="W1")
        self.wt2 = WasteTypeCatalog.objects.create(code="DIR02", value="W2")
        self.wt3 = WasteTypeCatalog.objects.create(code="DIR03", value="W3")
        self.suf1 = SuffixCatalog.objects.create(value="SD1")
        self.suf2 = SuffixCatalog.objects.create(value="SD2")
        self.suf3 = SuffixCatalog.objects.create(value="SD3")

        self.pair_only_3h = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile, waste_type=self.wt1, suffix=self.suf1,
        )
        self.pair_only_3h.yard_vehicle_kinds.set([self.vk_3h])

        self.pair_only_h = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile, waste_type=self.wt2, suffix=self.suf2,
        )
        self.pair_only_h.yard_vehicle_kinds.set([self.vk_h])

        self.pair_h_and_3h = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile, waste_type=self.wt3, suffix=self.suf3,
        )
        self.pair_h_and_3h.yard_vehicle_kinds.set([self.vk_h, self.vk_3h])

        self.rz_h = VehicleRzCatalog.objects.create(value="RZDIRH")
        self.prof_h = VehicleRzProfile.objects.create(rz=self.rz_h)
        self.prof_h.vehicle_kinds.add(self.vk_h)

        self.rz_3h = VehicleRzCatalog.objects.create(value="RZDIR3H")
        self.prof_3h = VehicleRzProfile.objects.create(rz=self.rz_3h)
        self.prof_3h.vehicle_kinds.add(self.vk_3h)

    def test_vehicle_kind_covers_task_dynamic_tree(self):
        self.assertFalse(vehicle_kind_covers_task(self.vk_3h.pk, self.vk_h.pk))
        self.assertTrue(vehicle_kind_covers_task(self.vk_h.pk, self.vk_3h.pk))
        self.assertTrue(vehicle_kind_covers_task(self.vk_3h.pk, self.vk_4h.pk))

    def test_rz_profile_serves_task_kind_directional(self):
        self.assertFalse(rz_profile_serves_task_kind(self.prof_h, self.vk_3h.pk))
        self.assertTrue(rz_profile_serves_task_kind(self.prof_h, self.vk_h.pk))
        self.assertTrue(rz_profile_serves_task_kind(self.prof_3h, self.vk_h.pk))

    def test_rz_profile_serves_pair_scenarios(self):
        self.assertFalse(rz_profile_serves_pair(self.prof_h, self.pair_only_3h))
        self.assertTrue(rz_profile_serves_pair(self.prof_3h, self.pair_only_3h))
        self.assertTrue(rz_profile_serves_pair(self.prof_3h, self.pair_only_h))
        self.assertTrue(rz_profile_serves_pair(self.prof_h, self.pair_h_and_3h))

    def test_pair_covering_and_hint(self):
        only_3h = pair_covering_vehicle_kind_ids(self.pair_only_3h)
        self.assertNotIn(self.vk_h.pk, only_3h)
        self.assertIn(self.vk_4h.pk, only_3h)
        hint = pair_vehicle_kind_constraint_hint(self.pair_only_3h)
        self.assertIn("přeplánování", hint or "")
        self.assertIsNone(pair_vehicle_kind_constraint_hint(self.pair_h_and_3h))

    def test_mismatch_message(self):
        msg = rz_profile_pair_mismatch_message(self.prof_h, self.pair_only_3h, vehicle_rz_label="RZDIRH")
        self.assertIn("přeplánovat", msg or "")

    def test_passport_h_invalid_for_task_3h(self):
        from catalogs.models import ContainerPassport

        passport = ContainerPassport.objects.create(
            container_number="PDIR-H-01",
            vehicle_kind=self.vk_h,
            color="—",
        )
        self.assertFalse(
            passport_matches_vehicle_rz_compat(passport, self.rz_h, task_kind_id=self.vk_3h.pk)
        )
