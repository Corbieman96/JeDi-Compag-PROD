"""Historie pohybu kontejneru — service a view."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    AddressCatalog,
    ContainerPassport,
    IcoCatalog,
    NameCatalog,
    SuffixCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleKindCatalog
from catalogs.services.container_passport_history import container_passport_ride_history
from waste_docs.models import Pruvodka


class ContainerPassportHistoryServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("cp_hist", password="pw")
        self.vk = VehicleKindCatalog.objects.create(name="Hák", shortcut="H", sort_order=0)
        self.passport = ContainerPassport.objects.create(
            vehicle_kind=self.vk, container_number="K-100"
        )
        self.other_passport = ContainerPassport.objects.create(
            vehicle_kind=self.vk, container_number="K-200"
        )
        self.base = {
            "name": NameCatalog.objects.create(value="Subjekt"),
            "ico": IcoCatalog.objects.create(value="12345678"),
            "address": AddressCatalog.objects.create(value="Adresa 1"),
            "waste_type": WasteTypeCatalog.objects.create(code="200101", value="Wt"),
            "waste_code": WasteCodeCatalog.objects.create(value="WC"),
            "waste_category": WasteCategoryCatalog.objects.create(value="O"),
            "suffix": SuffixCatalog.objects.create(value="SFX"),
            "created_by": self.user,
        }

    def _ride(self, **extra) -> Pruvodka:
        data = dict(self.base)
        data.update(extra)
        data.setdefault("container_number", "")
        return Pruvodka.objects.create(**data)

    def test_history_includes_fk_and_number_matches(self):
        r_fk = self._ride(
            container_passport=self.passport, drive_date=date(2026, 7, 1)
        )
        r_num = self._ride(container_number="K-100", drive_date=date(2026, 7, 2))
        r_num2 = self._ride(
            container_number="", container_number_2="k-100", drive_date=date(2026, 7, 3)
        )
        self._ride(container_number="K-200", drive_date=date(2026, 7, 1))

        rides = container_passport_ride_history(self.passport)
        pks = {r.pk for r in rides}
        self.assertIn(r_fk.pk, pks)
        self.assertIn(r_num.pk, pks)
        self.assertIn(r_num2.pk, pks)
        self.assertEqual(len(rides), 3)

    def test_history_orders_newest_first(self):
        old = self._ride(container_passport=self.passport, drive_date=date(2026, 6, 1))
        new = self._ride(container_passport=self.passport, drive_date=date(2026, 7, 1))
        rides = container_passport_ride_history(self.passport)
        self.assertEqual(rides[0].pk, new.pk)
        self.assertEqual(rides[-1].pk, old.pk)

    def test_history_includes_archived(self):
        archived = self._ride(
            container_passport=self.passport,
            drive_date=date(2026, 7, 1),
            is_archived=True,
        )
        rides = container_passport_ride_history(self.passport)
        self.assertIn(archived.pk, {r.pk for r in rides})

    def test_history_no_duplicates_when_fk_and_number_match(self):
        both = self._ride(
            container_passport=self.passport,
            container_number="K-100",
            drive_date=date(2026, 7, 1),
        )
        rides = container_passport_ride_history(self.passport)
        self.assertEqual([r.pk for r in rides].count(both.pk), 1)


class ContainerPassportHistoryViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser("cp_admin", password="pw")
        self.client = Client()
        self.client.force_login(self.admin)
        self.vk = VehicleKindCatalog.objects.create(name="Hák", shortcut="H", sort_order=0)
        self.passport = ContainerPassport.objects.create(
            vehicle_kind=self.vk, container_number="K-777"
        )

    def test_history_page_renders(self):
        url = reverse("catalogs:container_passport_history", args=[self.passport.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "K-777")

    def test_history_page_404_for_missing(self):
        url = reverse("catalogs:container_passport_history", args=[999999])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)
