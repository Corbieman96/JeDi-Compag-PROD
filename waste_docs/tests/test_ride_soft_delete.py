"""Bezpečné smazání jízdy (soft delete + audit log)."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile
from waste_docs.models import Pruvodka, PruvodkaSoftDeleteLog
from waste_docs.services.ride_soft_delete import RideSoftDeleteError, soft_delete_pruvodka


class RideSoftDeleteTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("soft_del_admin", password="pw", is_superuser=True)
        self.other = User.objects.create_user("soft_del_other", password="pw")
        self.client = Client()
        self.day = date(2026, 7, 1)
        self.activity = ActivityCatalog.objects.create(name="Svoz soft delete")
        self.driver = DriverProfile.objects.create(personal_number="SD1", last_name="Driver")
        self.rz = VehicleRzCatalog.objects.create(value="1S55555")
        VehicleRzProfile.objects.create(rz=self.rz)
        name = NameCatalog.objects.create(value="Subjekt soft delete")
        self.common = dict(
            name=name,
            ico=IcoCatalog.objects.create(value="55667788"),
            address=AddressCatalog.objects.create(value="Adr soft"),
            waste_type=WasteTypeCatalog.objects.create(code="770077", value="Wsd"),
            waste_code=WasteCodeCatalog.objects.create(value="WCSD"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOSD"),
            suffix=SuffixCatalog.objects.create(value="SFXSD"),
            activity=self.activity,
            drive_date=self.day,
            vehicle_rz=self.rz,
            driver=self.driver,
            created_by=self.admin,
            container_number="",
        )

    def _create_ride(self, **kwargs) -> Pruvodka:
        ride = Pruvodka(**{**self.common, **kwargs})
        ride.save()
        return ride

    def test_soft_delete_requires_reason(self):
        ride = self._create_ride()
        with self.assertRaises(RideSoftDeleteError):
            soft_delete_pruvodka(pruvodka=ride, actor=self.admin, reason="ab")

    def test_soft_delete_archives_and_creates_log(self):
        ride = self._create_ride()
        snd = ride.snd_cislo_listu
        log = soft_delete_pruvodka(
            pruvodka=ride,
            actor=self.admin,
            reason="Duplicitní záznam z testu",
        )
        ride.refresh_from_db()
        self.assertTrue(ride.is_archived)
        self.assertEqual(ride.archive_reason, "Duplicitní záznam z testu")
        self.assertEqual(log.snd_cislo_listu, snd)
        self.assertEqual(PruvodkaSoftDeleteLog.objects.filter(pruvodka=ride).count(), 1)

    def test_confirm_view_requires_reason_on_post(self):
        ride = self._create_ride()
        self.client.force_login(self.admin)
        url = reverse("waste_docs:ride_soft_delete_confirm", kwargs={"pk": ride.pk})
        response = self.client.post(url, {"reason": "krát"})
        self.assertEqual(response.status_code, 200)
        ride.refresh_from_db()
        self.assertFalse(ride.is_archived)

    def test_confirm_view_soft_deletes_with_reason(self):
        ride = self._create_ride()
        self.client.force_login(self.admin)
        url = reverse("waste_docs:ride_soft_delete_confirm", kwargs={"pk": ride.pk})
        response = self.client.post(url, {"reason": "Chybně založená jízda"})
        self.assertEqual(response.status_code, 302)
        ride.refresh_from_db()
        self.assertTrue(ride.is_archived)

    def test_log_list_searchable_by_snd(self):
        ride = self._create_ride()
        soft_delete_pruvodka(pruvodka=ride, actor=self.admin, reason="Test dohledání v logu")
        self.client.force_login(self.admin)
        url = reverse("waste_docs:ride_soft_delete_log_list")
        response = self.client.get(url, {"q": ride.snd_cislo_listu})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ride.snd_cislo_listu)
        self.assertContains(response, "Test dohledání v logu")

    def test_archived_detail_visible_for_admin(self):
        ride = self._create_ride()
        soft_delete_pruvodka(pruvodka=ride, actor=self.admin, reason="Archiv pro náhled")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("waste_docs:detail", kwargs={"pk": ride.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jízda byla smazána")

    def test_archive_without_reason_redirects_to_confirm(self):
        ride = self._create_ride()
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("waste_docs:archive", kwargs={"pk": ride.pk}),
            {"archive_reason": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("waste_docs:ride_soft_delete_confirm", kwargs={"pk": ride.pk}),
        )

    def test_blocks_follow_up_child_delete(self):
        parent = self._create_ride()
        child = self._create_ride(follow_up_parent=parent)
        with self.assertRaises(RideSoftDeleteError):
            soft_delete_pruvodka(pruvodka=parent, actor=self.admin, reason="Mazání rodiče")
