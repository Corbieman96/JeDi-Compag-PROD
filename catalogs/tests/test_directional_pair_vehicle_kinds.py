"""Směrová kompatibilita druhů vozidel u páru F/P (H / 3H a obecný strom)."""

from django.test import TestCase

from catalogs.models import (
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
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
    vehicle_kind_covers_task,
)
from catalogs.models import VehicleRzCatalog


class DirectionalPairVehicleKindTests(TestCase):
    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        self.vk_h = VehicleKindCatalog.objects.create(name="Hák", shortcut="H", sort_order=1)
        self.vk_3h = VehicleKindCatalog.objects.create(
            name="Tříosý hák", shortcut="3H", sort_order=2, parent_kind=self.vk_h
        )
        self.vk_4h = VehicleKindCatalog.objects.create(
            name="Čtyřosý hák", shortcut="4H", sort_order=3, parent_kind=self.vk_3h
        )
        clear_vehicle_kind_compatibility_cache()

        self.profile = NameSubjectProfile.objects.create(
            name=NameCatalog.objects.create(value="Subj dir"),
        )
        self.wt1 = WasteTypeCatalog.objects.create(code="D01", value="W1")
        self.wt2 = WasteTypeCatalog.objects.create(code="D02", value="W2")
        self.wt3 = WasteTypeCatalog.objects.create(code="D03", value="W3")
        self.suf1 = SuffixCatalog.objects.create(value="S1")
        self.suf2 = SuffixCatalog.objects.create(value="S2")
        self.suf3 = SuffixCatalog.objects.create(value="S3")

        self.pair_only_3h = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt1,
            suffix=self.suf1,
        )
        self.pair_only_3h.yard_vehicle_kinds.set([self.vk_3h])

        self.pair_only_h = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt2,
            suffix=self.suf2,
        )
        self.pair_only_h.yard_vehicle_kinds.set([self.vk_h])

        self.pair_h_and_3h = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt3,
            suffix=self.suf3,
        )
        self.pair_h_and_3h.yard_vehicle_kinds.set([self.vk_h, self.vk_3h])

        self.rz_h = VehicleRzCatalog.objects.create(value="RZH")
        self.prof_h = VehicleRzProfile.objects.create(rz=self.rz_h)
        self.prof_h.vehicle_kinds.add(self.vk_h)

        self.rz_3h = VehicleRzCatalog.objects.create(value="RZ3H")
        self.prof_3h = VehicleRzProfile.objects.create(rz=self.rz_3h)
        self.prof_3h.vehicle_kinds.add(self.vk_3h)

    def test_vehicle_kind_covers_task_dynamic_tree(self):
        self.assertFalse(vehicle_kind_covers_task(self.vk_3h.pk, self.vk_h.pk))
        self.assertTrue(vehicle_kind_covers_task(self.vk_h.pk, self.vk_3h.pk))
        self.assertTrue(vehicle_kind_covers_task(self.vk_3h.pk, self.vk_4h.pk))

    def test_rz_profile_serves_pair_only_3h(self):
        self.assertFalse(rz_profile_serves_pair(self.prof_h, self.pair_only_3h))
        self.assertTrue(rz_profile_serves_pair(self.prof_3h, self.pair_only_3h))

    def test_rz_profile_serves_pair_only_h(self):
        self.assertTrue(rz_profile_serves_pair(self.prof_h, self.pair_only_h))
        self.assertTrue(rz_profile_serves_pair(self.prof_3h, self.pair_only_h))

    def test_rz_profile_serves_pair_h_and_3h(self):
        self.assertTrue(rz_profile_serves_pair(self.prof_h, self.pair_h_and_3h))
        self.assertTrue(rz_profile_serves_pair(self.prof_3h, self.pair_h_and_3h))

    def test_pair_covering_kind_ids(self):
        only_3h = pair_covering_vehicle_kind_ids(self.pair_only_3h)
        self.assertIn(self.vk_3h.pk, only_3h)
        self.assertIn(self.vk_4h.pk, only_3h)
        self.assertNotIn(self.vk_h.pk, only_3h)

        only_h = pair_covering_vehicle_kind_ids(self.pair_only_h)
        self.assertIn(self.vk_h.pk, only_h)
        self.assertIn(self.vk_3h.pk, only_h)

    def test_constraint_hint_single_kind(self):
        hint = pair_vehicle_kind_constraint_hint(self.pair_only_3h)
        self.assertIsNotNone(hint)
        self.assertIn("3H", hint)
        self.assertIn("přeplánování", hint)
        self.assertIsNone(pair_vehicle_kind_constraint_hint(self.pair_h_and_3h))

    def test_mismatch_message_only_3h_with_h_rz(self):
        msg = rz_profile_pair_mismatch_message(
            self.prof_h, self.pair_only_3h, vehicle_rz_label="RZH"
        )
        self.assertIsNotNone(msg)
        self.assertIn("přeplánovat", msg)
        self.assertIsNone(
            rz_profile_pair_mismatch_message(self.prof_3h, self.pair_only_3h, vehicle_rz_label="RZ3H")
        )
