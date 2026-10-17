"""Počty jízd za den podle druhu vozidla — service a stránka nové jízdy."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models import DriverProfile
from catalogs.models.vehicle_rz import VehicleKindCatalog, VehicleRzProfile
from catalogs.services.vehicle_kind_compatibility import clear_vehicle_kind_compatibility_cache
from users.constants import ROLE_DISPECER, ROLE_RIDIC
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka
from waste_docs.services.pruvodka_day_kind_counts import ride_counts_by_vehicle_kind_bucket


class PruvodkaDayKindCountsServiceTests(TestCase):
    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        User = get_user_model()
        self.dispecer = User.objects.create_user("day_kind_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.day = date(2026, 7, 1)

        self.vk_r = VehicleKindCatalog.objects.create(name="Řetěz", shortcut="R", sort_order=0)
        self.vk_a = VehicleKindCatalog.objects.create(name="Atego", shortcut="A", sort_order=1)
        self.vk_h = VehicleKindCatalog.objects.create(name="Hák", shortcut="H", sort_order=2)
        self.vk_3h = VehicleKindCatalog.objects.create(
            name="Tříosý hák",
            shortcut="3H",
            sort_order=3,
            parent_kind=self.vk_h,
        )
        clear_vehicle_kind_compatibility_cache()

        self.name = NameCatalog.objects.create(value="Subjekt day kind")
        self.base = {
            "name": self.name,
            "ico": IcoCatalog.objects.create(value="99887766"),
            "address": AddressCatalog.objects.create(value="Adr day kind"),
            "waste_type": WasteTypeCatalog.objects.create(code="990098", value="Wdk"),
            "waste_code": WasteCodeCatalog.objects.create(value="WCDK"),
            "waste_category": WasteCategoryCatalog.objects.create(value="KODK"),
            "suffix": SuffixCatalog.objects.create(value="SFXDK"),
            "drive_date": self.day,
            "created_by": self.dispecer,
        }

        self.rz_r = self._rz_with_kinds("RZ-R1", self.vk_r)
        self.rz_r2 = self._rz_with_kinds("RZ-R2", self.vk_r)
        self.rz_a = self._rz_with_kinds("RZ-A1", self.vk_a)
        self.rz_3h = self._rz_with_kinds("RZ-3H1", self.vk_3h)
        self.rz_rh = self._rz_with_kinds("RZ-RH", self.vk_r, self.vk_h)

    def _rz_with_kinds(self, value: str, *kinds: VehicleKindCatalog) -> VehicleRzCatalog:
        rz = VehicleRzCatalog.objects.create(value=value)
        prof = VehicleRzProfile.objects.create(rz=rz)
        prof.vehicle_kinds.set(kinds)
        return rz

    def _ride(self, *, vehicle_rz: VehicleRzCatalog | None = None, **extra) -> Pruvodka:
        return Pruvodka.objects.create(**self.base, vehicle_rz=vehicle_rz, container_number="", **extra)

    def _count(self, key: str) -> int:
        summary = ride_counts_by_vehicle_kind_bucket(self.dispecer, self.day)
        return next(row.count for row in summary.rows if row.key == key)

    def test_counts_by_bucket_and_total(self):
        self._ride(vehicle_rz=self.rz_r)
        self._ride(vehicle_rz=self.rz_r2)
        self._ride(vehicle_rz=self.rz_a)
        self._ride(vehicle_rz=self.rz_3h)
        self._ride(vehicle_rz=None)

        summary = ride_counts_by_vehicle_kind_bucket(self.dispecer, self.day)
        self.assertEqual(self._count("retez"), 2)
        self.assertEqual(self._count("atego"), 1)
        self.assertEqual(self._count("hak"), 1)
        self.assertEqual(summary.total, 5)
        self.assertEqual(summary.unclassified, 1)

    def test_blank_pruvodka_excluded_from_total(self):
        self._ride(vehicle_rz=self.rz_r)
        self._ride(vehicle_rz=None, is_blank_pruvodka=True)

        summary = ride_counts_by_vehicle_kind_bucket(self.dispecer, self.day)
        self.assertEqual(summary.total, 1)
        self.assertEqual(self._count("retez"), 1)
        self.assertEqual(summary.unclassified, 0)

    def test_fallback_driver_kinds_when_rz_profile_empty(self):
        rz = VehicleRzCatalog.objects.create(value="RZ-NOKIND")
        VehicleRzProfile.objects.create(rz=rz)
        driver = DriverProfile.objects.create(
            personal_number="DK001",
            first_name="Jan",
            last_name="Řidič",
        )
        driver.allowed_vehicle_kinds.add(self.vk_h)
        self._ride(vehicle_rz=rz, driver=driver)

        summary = ride_counts_by_vehicle_kind_bucket(self.dispecer, self.day)
        self.assertEqual(summary.total, 1)
        self.assertEqual(self._count("hak"), 1)
        self.assertEqual(summary.unclassified, 0)

    def test_priority_retez_over_hak(self):
        self._ride(vehicle_rz=self.rz_rh)
        summary = ride_counts_by_vehicle_kind_bucket(self.dispecer, self.day)
        self.assertEqual(self._count("retez"), 1)
        self.assertEqual(self._count("hak"), 0)
        self.assertEqual(summary.total, 1)
        self.assertEqual(summary.unclassified, 0)

    def test_archived_rides_excluded(self):
        ride = self._ride(vehicle_rz=self.rz_r)
        ride.is_archived = True
        ride.save(update_fields=("is_archived",))
        summary = ride_counts_by_vehicle_kind_bucket(self.dispecer, self.day)
        self.assertEqual(summary.total, 0)

    def test_non_dispatcher_sees_only_own_rides(self):
        User = get_user_model()
        other = User.objects.create_user("day_kind_other", password="pw")
        set_user_role(other, ROLE_RIDIC)
        self._ride(vehicle_rz=self.rz_r)
        other_base = {**self.base, "created_by": other}
        Pruvodka.objects.create(**other_base, vehicle_rz=self.rz_r, container_number="")

        summary_disp = ride_counts_by_vehicle_kind_bucket(self.dispecer, self.day)
        summary_other = ride_counts_by_vehicle_kind_bucket(other, self.day)
        self.assertEqual(summary_disp.total, 2)
        self.assertEqual(summary_other.total, 1)


class PruvodkaDayKindCountsViewTests(TestCase):
    databases = {"default", "addresses"}
    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        User = get_user_model()
        self.dispecer = User.objects.create_user("day_kind_view_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.day = date(2026, 7, 1)

        self.vk_r = VehicleKindCatalog.objects.create(name="Řetěz view", shortcut="R", sort_order=0)
        clear_vehicle_kind_compatibility_cache()

        name = NameCatalog.objects.create(value="Subjekt day kind view")
        base = {
            "name": name,
            "ico": IcoCatalog.objects.create(value="88776655"),
            "address": AddressCatalog.objects.create(value="Adr day kind view"),
            "waste_type": WasteTypeCatalog.objects.create(code="990099", value="Wdkv"),
            "waste_code": WasteCodeCatalog.objects.create(value="WCDKV"),
            "waste_category": WasteCategoryCatalog.objects.create(value="KODKV"),
            "suffix": SuffixCatalog.objects.create(value="SFXDKV"),
            "drive_date": self.day,
            "container_number": "",
        }
        rz = VehicleRzCatalog.objects.create(value="RZ-VIEW-R")
        prof = VehicleRzProfile.objects.create(rz=rz)
        prof.vehicle_kinds.add(self.vk_r)

        Pruvodka.objects.create(**base, vehicle_rz=rz, created_by=self.dispecer)
        Pruvodka.objects.create(**base, vehicle_rz=rz, created_by=self.dispecer)

    def test_create_page_shows_day_kind_table(self):
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:create") + f"?date={self.day.isoformat()}"
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jízdy v den")
        self.assertContains(response, "Řetěz")
        self.assertContains(response, "Atego")
        self.assertContains(response, "Hák")
        self.assertContains(response, "Celkem")
        self.assertContains(response, ">2<")
        self.assertNotContains(response, "bez přiřazeného druhu vozidla")
