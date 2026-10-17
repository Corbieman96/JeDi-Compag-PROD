"""Hromadná výměna řidiče / RZ ve skupině jízd."""

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
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile
from core.services.ride_grouping import ride_group_key
from waste_docs.models import Pruvodka
from waste_docs.services.ride_reassign_driver.apply import apply_ride_reassign_driver
from waste_docs.services.ride_reassign_driver.eligibility import (
    driver_rz_options_map,
    eligible_rz_for_driver,
    validate_driver_and_rz,
)


class RideReassignDriverTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("reassign_u", password="pw", is_superuser=True)
        self.client = Client()
        self.client.force_login(self.user)

        self.name = NameCatalog.objects.create(value="Subjekt reassign")
        self.ico = IcoCatalog.objects.create(value="11223344")
        self.addr = AddressCatalog.objects.create(value="Ulice 1")
        self.wt = WasteTypeCatalog.objects.create(code="200301", value="Odpad reassign")
        self.wc = WasteCodeCatalog.objects.create(value="20 03 01")
        self.wcat = WasteCategoryCatalog.objects.create(value="O")
        self.suf = SuffixCatalog.objects.create(value="Koncovka R")
        self.activity = ActivityCatalog.objects.create(name="Aktivita reassign")

        self.vk = VehicleKindCatalog.objects.create(name="Hák R", shortcut="HaR", sort_order=1)
        self.rz = VehicleRzCatalog.objects.create(value="5SB5766")
        self.rz_other = VehicleRzCatalog.objects.create(value="5SB9999")
        for rz in (self.rz, self.rz_other):
            prof = VehicleRzProfile.objects.create(rz=rz)
            prof.vehicle_kinds.add(self.vk)

        self.driver = DriverProfile.objects.create(
            personal_number="R1", first_name="Oto", last_name="Hlaváček"
        )
        self.driver.allowed_vehicle_kinds.add(self.vk)
        self.driver.allowed_vehicle_rz.add(self.rz.profile, self.rz_other.profile)

        self.driver2 = DriverProfile.objects.create(
            personal_number="R2", first_name="Jan", last_name="Novák"
        )
        self.driver2.allowed_vehicle_kinds.add(self.vk)
        self.driver2.allowed_vehicle_rz.add(self.rz.profile, self.rz_other.profile)

        self.driver_wrong = DriverProfile.objects.create(
            personal_number="R3", first_name="Petr", last_name="BezDruhu"
        )

        self.day = date(2026, 8, 14)
        self.ride_a = self._make_ride()
        self.ride_b = self._make_ride()
        self.ride_other_group = self._make_ride(driver=self.driver2)

    def _make_ride(self, *, driver=None, rz=None):
        return Pruvodka.objects.create(
            activity=self.activity,
            drive_date=self.day,
            name=self.name,
            ico=self.ico,
            address=self.addr,
            waste_type=self.wt,
            waste_code=self.wc,
            waste_category=self.wcat,
            suffix=self.suf,
            vehicle_rz=rz or self.rz,
            driver=driver or self.driver,
            created_by=self.user,
        )

    def test_reject_driver_without_kind(self):
        err = validate_driver_and_rz(
            driver_id=self.driver_wrong.pk,
            vehicle_rz_id=self.rz.pk,
            vehicle_kind_id=self.vk.pk,
        )
        self.assertIsNotNone(err)

    def test_reject_peer_outside_group(self):
        result = apply_ride_reassign_driver(
            user=self.user,
            drive_date=self.day,
            from_vehicle_rz_id=self.rz.pk,
            from_driver_id=self.driver.pk,
            selected_pks=[self.ride_a.pk, self.ride_other_group.pk],
            new_driver_id=self.driver2.pk,
            new_vehicle_rz_id=None,
        )
        self.assertFalse(result.ok)
        self.ride_a.refresh_from_db()
        self.assertEqual(self.ride_a.driver_id, self.driver.pk)

    def test_bulk_reassign_keeps_rz_and_snapshots(self):
        result = apply_ride_reassign_driver(
            user=self.user,
            drive_date=self.day,
            from_vehicle_rz_id=self.rz.pk,
            from_driver_id=self.driver.pk,
            selected_pks=[self.ride_a.pk, self.ride_b.pk],
            new_driver_id=self.driver2.pk,
            new_vehicle_rz_id=None,
        )
        self.assertTrue(result.ok, result.message)
        self.assertEqual(result.updated_count, 2)
        for ride in (self.ride_a, self.ride_b):
            ride.refresh_from_db()
            self.assertEqual(ride.driver_id, self.driver2.pk)
            self.assertEqual(ride.vehicle_rz_id, self.rz.pk)
            self.assertIn("Novák", ride.driver_snapshot)
            self.assertEqual(ride.vehicle_rz_snapshot, "5SB5766")

        expected_key = ride_group_key(self.day, self.rz.pk, self.driver2.pk)
        self.assertIn(expected_key, result.redirect_url)

    def test_reassign_with_new_rz(self):
        result = apply_ride_reassign_driver(
            user=self.user,
            drive_date=self.day,
            from_vehicle_rz_id=self.rz.pk,
            from_driver_id=self.driver.pk,
            selected_pks=[self.ride_a.pk],
            new_driver_id=self.driver2.pk,
            new_vehicle_rz_id=self.rz_other.pk,
        )
        self.assertTrue(result.ok, result.message)
        self.ride_a.refresh_from_db()
        self.assertEqual(self.ride_a.driver_id, self.driver2.pk)
        self.assertEqual(self.ride_a.vehicle_rz_id, self.rz_other.pk)
        self.assertEqual(self.ride_a.vehicle_rz_snapshot, "5SB9999")

    def test_post_endpoint_success(self):
        url = reverse("waste_docs:ride_reassign_driver")
        resp = self.client.post(
            url,
            {
                "drive_date": self.day.isoformat(),
                "from_vehicle_rz_id": str(self.rz.pk),
                "from_driver_id": str(self.driver.pk),
                "new_driver_id": str(self.driver2.pk),
                "new_vehicle_rz_id": str(self.rz.pk),
                "ride_pks": [str(self.ride_a.pk)],
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.ride_a.refresh_from_db()
        self.assertEqual(self.ride_a.driver_id, self.driver2.pk)

    def test_dashboard_shows_reassign_button(self):
        key = ride_group_key(self.day, self.rz.pk, self.driver.pk)
        url = f"{reverse('core:dashboard')}?date={self.day.isoformat()}&ride_group={key}"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Výměna řidiče")
        self.assertContains(resp, "ride-reassign-driver-open")

    def test_driver_rz_options_include_all_kinds(self):
        vk_b = VehicleKindCatalog.objects.create(name="Atea R", shortcut="AtR", sort_order=2)
        rz_b = VehicleRzCatalog.objects.create(value="1AT1111")
        prof_b = VehicleRzProfile.objects.create(rz=rz_b, vehicle_type="poznámka Atea")
        prof_b.vehicle_kinds.add(vk_b)

        self.driver2.allowed_vehicle_kinds.add(vk_b)
        # nespárovaná RZ jiného druhu musí být v nabídce

        rzs = eligible_rz_for_driver(self.driver2)
        values = {r.value for r in rzs}
        self.assertIn("5SB5766", values)
        self.assertIn("5SB9999", values)
        self.assertIn("1AT1111", values)

        options = driver_rz_options_map(drivers=[self.driver2])
        labels = {row["label"] for row in options[self.driver2.pk]}
        self.assertTrue(any("1AT1111" in lab and "AtR" in lab for lab in labels))

    def test_reassign_to_unpaired_rz_of_other_kind(self):
        vk_b = VehicleKindCatalog.objects.create(name="Atea R2", shortcut="AtR2", sort_order=3)
        rz_b = VehicleRzCatalog.objects.create(value="2AT2222")
        prof_b = VehicleRzProfile.objects.create(rz=rz_b, vehicle_type="jiný druh")
        prof_b.vehicle_kinds.add(vk_b)
        self.driver2.allowed_vehicle_kinds.add(vk_b)

        result = apply_ride_reassign_driver(
            user=self.user,
            drive_date=self.day,
            from_vehicle_rz_id=self.rz.pk,
            from_driver_id=self.driver.pk,
            selected_pks=[self.ride_a.pk],
            new_driver_id=self.driver2.pk,
            new_vehicle_rz_id=rz_b.pk,
        )
        self.assertTrue(result.ok, result.message)
        self.ride_a.refresh_from_db()
        self.assertEqual(self.ride_a.driver_id, self.driver2.pk)
        self.assertEqual(self.ride_a.vehicle_rz_id, rz_b.pk)
        self.assertEqual(self.ride_a.vehicle_rz_snapshot, "2AT2222")
