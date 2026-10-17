"""Kompatibilita druhů vozidel — strom a M2M."""

from django.test import TestCase

from catalogs.models import VehicleKindCatalog
from catalogs.models.vehicle_rz import VehicleRzProfile
from catalogs.services.vehicle_kind_compatibility import (
    clear_vehicle_kind_compatibility_cache,
    compatible_kind_ids,
    passport_matches_vehicle_rz_compat,
    rz_profile_serves_task_kind,
)
from catalogs.models import VehicleRzCatalog


class VehicleKindCompatibilityTests(TestCase):
    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        self.vk_a = VehicleKindCatalog.objects.create(name="Typ A", shortcut="A", sort_order=0)
        self.vk_h = VehicleKindCatalog.objects.create(
            name="Hák",
            shortcut="H",
            sort_order=1,
            parent_kind=self.vk_a,
        )
        self.vk_3h = VehicleKindCatalog.objects.create(
            name="Tříosý hák",
            shortcut="3H",
            sort_order=2,
            parent_kind=self.vk_h,
        )
        self.vk_r = VehicleKindCatalog.objects.create(name="Řetěz", shortcut="R", sort_order=3)
        clear_vehicle_kind_compatibility_cache()

    def test_compatible_includes_ancestors_and_descendants(self):
        h_set = compatible_kind_ids(self.vk_h.pk)
        self.assertIn(self.vk_h.pk, h_set)
        self.assertIn(self.vk_a.pk, h_set)
        self.assertIn(self.vk_3h.pk, h_set)
        self.assertNotIn(self.vk_r.pk, h_set)

        three_set = compatible_kind_ids(self.vk_3h.pk)
        self.assertIn(self.vk_3h.pk, three_set)
        self.assertIn(self.vk_h.pk, three_set)
        self.assertIn(self.vk_a.pk, three_set)

    def test_extra_compatible_m2m(self):
        clear_vehicle_kind_compatibility_cache()
        self.vk_r.extra_compatible_kinds.add(self.vk_h)
        clear_vehicle_kind_compatibility_cache()
        r_set = compatible_kind_ids(self.vk_r.pk)
        self.assertIn(self.vk_h.pk, r_set)

    def test_rz_profile_serves_task_kind(self):
        rz = VehicleRzCatalog.objects.create(value="TSTRZ")
        prof = VehicleRzProfile.objects.create(rz=rz)
        prof.vehicle_kinds.add(self.vk_h)
        self.assertFalse(rz_profile_serves_task_kind(prof, self.vk_3h.pk))
        self.assertTrue(rz_profile_serves_task_kind(prof, self.vk_h.pk))
        prof.vehicle_kinds.set([self.vk_r])
        clear_vehicle_kind_compatibility_cache()
        self.assertFalse(rz_profile_serves_task_kind(prof, self.vk_h.pk))

    def test_passport_h_invalid_for_task_3h(self):
        from catalogs.models import ContainerPassport

        rz = VehicleRzCatalog.objects.create(value="TSTRZ2")
        prof = VehicleRzProfile.objects.create(rz=rz)
        prof.vehicle_kinds.add(self.vk_h)
        passport = ContainerPassport.objects.create(
            container_number="P-H-01",
            vehicle_kind=self.vk_h,
            color="—",
        )
        self.assertFalse(
            passport_matches_vehicle_rz_compat(passport, rz, task_kind_id=self.vk_3h.pk)
        )

    def test_follow_up_covers_parent_kind_direction(self):
        from catalogs.services.vehicle_kind_compatibility import follow_up_covers_parent_kind

        self.assertTrue(follow_up_covers_parent_kind(self.vk_h.pk, self.vk_3h.pk))
        self.assertFalse(follow_up_covers_parent_kind(self.vk_3h.pk, self.vk_h.pk))
        self.assertFalse(follow_up_covers_parent_kind(self.vk_a.pk, self.vk_h.pk))
