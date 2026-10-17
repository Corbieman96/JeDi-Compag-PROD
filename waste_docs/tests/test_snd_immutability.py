"""Regrese: přidělené SND zůstává neměnné ve všech běžných save cestách."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

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
from waste_docs.models import Pruvodka


class SndImmutabilityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("snd_immut", password="pw", is_superuser=True)
        self.day = date(2026, 6, 23)
        self.activity_snd = ActivityCatalog.objects.create(name="Svoz SND immut")
        self.activity_other = ActivityCatalog.objects.create(name="Jiná SND immut")
        self.driver = DriverProfile.objects.create(personal_number="IM1", last_name="Driver")
        self.rz = VehicleRzCatalog.objects.create(value="1S33333")
        self.rz_other = VehicleRzCatalog.objects.create(value="1S44444")
        VehicleRzProfile.objects.create(rz=self.rz)
        VehicleRzProfile.objects.create(rz=self.rz_other)
        name = NameCatalog.objects.create(value="Subjekt SND immut")
        self.common = dict(
            name=name,
            ico=IcoCatalog.objects.create(value="11223344"),
            address=AddressCatalog.objects.create(value="Adr immut"),
            waste_type=WasteTypeCatalog.objects.create(code="880088", value="Wim"),
            waste_code=WasteCodeCatalog.objects.create(value="WCIM"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOIM"),
            suffix=SuffixCatalog.objects.create(value="SFXIM"),
            activity=self.activity_snd,
            drive_date=self.day,
            vehicle_rz=self.rz,
            driver=self.driver,
            created_by=self.user,
            container_number="",
        )

    def _create_ride(self, **kwargs) -> Pruvodka:
        ride = Pruvodka(**{**self.common, **kwargs})
        ride.save()
        return ride

    def test_activity_change_keeps_snd(self):
        ride = self._create_ride()
        snd_before = ride.snd_cislo_listu
        self.assertTrue(snd_before)

        ride.activity = self.activity_other
        ride.save()
        ride.refresh_from_db()
        self.assertEqual(ride.snd_cislo_listu, snd_before)

    def test_save_update_fields_vehicle_rz_keeps_snd(self):
        ride = self._create_ride()
        snd_before = ride.snd_cislo_listu

        ride.vehicle_rz = self.rz_other
        ride.save(update_fields=["vehicle_rz_id"])
        ride.refresh_from_db()
        self.assertEqual(ride.snd_cislo_listu, snd_before)

    def test_save_update_fields_ride_route_order_keeps_snd(self):
        ride = self._create_ride()
        snd_before = ride.snd_cislo_listu

        ride.ride_route_order = 2
        ride.save(update_fields=["ride_route_order"])
        ride.refresh_from_db()
        self.assertEqual(ride.snd_cislo_listu, snd_before)
        self.assertEqual(ride.ride_route_order, 2)

    def test_tampered_snd_in_memory_restored_on_save(self):
        ride = self._create_ride()
        original_snd = ride.snd_cislo_listu
        original_group = ride.ride_group_number
        original_seq = ride.ride_sequence

        ride.snd_cislo_listu = "0000999-2026-99"
        ride.ride_group_number = 999
        ride.ride_sequence = 99
        ride.contact_note = "Změna obsahu"
        ride.save()
        ride.refresh_from_db()

        self.assertEqual(ride.snd_cislo_listu, original_snd)
        self.assertEqual(ride.ride_group_number, original_group)
        self.assertEqual(ride.ride_sequence, original_seq)
        self.assertEqual(ride.contact_note, "Změna obsahu")

    def test_new_ride_still_gets_snd(self):
        ride = self._create_ride()
        self.assertTrue((ride.snd_cislo_listu or "").strip())
        self.assertGreater(ride.ride_group_number, 0)
