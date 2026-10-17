"""Při úpravě jízdy zůstává SND neměnné; přiděluje se jen novým záznamům."""

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


class RideNumberingEditTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("snd_edit", password="pw", is_superuser=True)
        self.day_a = date(2026, 6, 22)
        self.day_b = date(2026, 6, 23)
        self.activity = ActivityCatalog.objects.create(name="Svoz SND edit")
        self.driver_a = DriverProfile.objects.create(personal_number="SND1", last_name="A")
        self.driver_b = DriverProfile.objects.create(personal_number="SND2", last_name="B")
        self.rz_a = VehicleRzCatalog.objects.create(value="1S11111")
        self.rz_b = VehicleRzCatalog.objects.create(value="1S22222")
        VehicleRzProfile.objects.create(rz=self.rz_a)
        VehicleRzProfile.objects.create(rz=self.rz_b)
        name = NameCatalog.objects.create(value="Subjekt SND edit")
        self.common = dict(
            name=name,
            ico=IcoCatalog.objects.create(value="99887766"),
            address=AddressCatalog.objects.create(value="Adr SND"),
            waste_type=WasteTypeCatalog.objects.create(code="990099", value="Wsnd"),
            waste_code=WasteCodeCatalog.objects.create(value="WCSN"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOSN"),
            suffix=SuffixCatalog.objects.create(value="SFXSN"),
            activity=self.activity,
            created_by=self.user,
            container_number="",
        )

    def _create_ride(self, **kwargs) -> Pruvodka:
        ride = Pruvodka(**{**self.common, **kwargs})
        ride.save()
        return ride

    def test_changing_drive_date_driver_vehicle_keeps_snd(self):
        ride = self._create_ride(
            drive_date=self.day_b,
            vehicle_rz=self.rz_b,
            driver=self.driver_b,
        )
        original_snd = ride.snd_cislo_listu
        original_group = ride.ride_group_number
        original_seq = ride.ride_sequence
        self.assertTrue(original_snd)

        ride.drive_date = self.day_a
        ride.driver = self.driver_a
        ride.vehicle_rz = self.rz_a
        ride.save()

        ride.refresh_from_db()
        self.assertEqual(ride.snd_cislo_listu, original_snd)
        self.assertEqual(ride.ride_group_number, original_group)
        self.assertEqual(ride.ride_sequence, original_seq)

    def test_edit_does_not_reassign_snd_to_other_driver_group(self):
        """Regrese: úprava řidiče/RZ nesmí přepsat existující číslo jinou skupinou."""
        ride = self._create_ride(
            drive_date=date(2026, 6, 23),
            vehicle_rz=self.rz_a,
            driver=self.driver_a,
        )
        original_snd = ride.snd_cislo_listu
        Pruvodka.objects.filter(pk=ride.pk).update(
            snd_cislo_listu="0000449-2026-8",
            ride_group_number=449,
            ride_sequence=8,
        )
        ride.refresh_from_db()

        other_group_ride = self._create_ride(
            drive_date=date(2026, 6, 23),
            vehicle_rz=self.rz_b,
            driver=self.driver_b,
        )
        self.assertNotEqual(other_group_ride.ride_group_number, 449)

        ride.driver = self.driver_b
        ride.vehicle_rz = self.rz_b
        ride.contact_note = "Úprava obsahu bez změny čísla"
        ride.save()
        ride.refresh_from_db()

        self.assertEqual(ride.snd_cislo_listu, "0000449-2026-8")
        self.assertEqual(ride.ride_group_number, 449)
        self.assertEqual(ride.ride_sequence, 8)
        self.assertNotEqual(ride.snd_cislo_listu, other_group_ride.snd_cislo_listu)

    def test_unchanged_grouping_keeps_snd_on_minor_edit(self):
        ride = self._create_ride(
            drive_date=self.day_a,
            vehicle_rz=self.rz_a,
            driver=self.driver_a,
        )
        snd_before = ride.snd_cislo_listu
        self.assertTrue(snd_before)
        ride.contact_note = "Likvidace železa"
        ride.save()
        ride.refresh_from_db()
        self.assertEqual(ride.snd_cislo_listu, snd_before)

    def test_same_driver_different_vehicles_get_distinct_groups(self):
        day = date(2026, 6, 26)
        ride_a = self._create_ride(
            drive_date=day,
            vehicle_rz=self.rz_a,
            driver=self.driver_a,
        )
        ride_b = self._create_ride(
            drive_date=day,
            vehicle_rz=self.rz_b,
            driver=self.driver_a,
        )
        self.assertNotEqual(ride_a.ride_group_number, ride_b.ride_group_number)
        self.assertEqual(ride_a.ride_sequence, 1)
        self.assertEqual(ride_b.ride_sequence, 1)
        self.assertTrue(ride_a.snd_cislo_listu.endswith("-1"))
        self.assertTrue(ride_b.snd_cislo_listu.endswith("-1"))

    def test_same_driver_same_vehicle_increments_sequence(self):
        day = date(2026, 6, 26)
        ride_first = self._create_ride(
            drive_date=day,
            vehicle_rz=self.rz_a,
            driver=self.driver_a,
        )
        ride_second = self._create_ride(
            drive_date=day,
            vehicle_rz=self.rz_a,
            driver=self.driver_a,
        )
        self.assertEqual(ride_first.ride_group_number, ride_second.ride_group_number)
        self.assertEqual(ride_first.ride_sequence, 1)
        self.assertEqual(ride_second.ride_sequence, 2)
        self.assertTrue(ride_first.snd_cislo_listu.endswith("-1"))
        self.assertTrue(ride_second.snd_cislo_listu.endswith("-2"))
