"""Dashboard — dva řidiči se stejnou RZ = dva řádky v Seznamu jízd."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
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
from core.services.dashboard_rides import build_dashboard_rides_section
from core.services.ride_grouping import ride_group_key
from users.constants import ROLE_ADMIN
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka


class DashboardRideListDriverSplitTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("dash_split_admin", password="pw", is_superuser=True)
        set_user_role(self.admin, ROLE_ADMIN)
        self.client = Client()
        self.client.force_login(self.admin)
        self.day = date(2026, 7, 20)
        self.rz = VehicleRzCatalog.objects.create(value="7S77777")
        self.driver_a = DriverProfile.objects.create(personal_number="SPL-A", last_name="Novák")
        self.driver_b = DriverProfile.objects.create(personal_number="SPL-B", last_name="Svoboda")
        common = dict(
            name=NameCatalog.objects.create(value="Subj split dash"),
            ico=IcoCatalog.objects.create(value="88776655"),
            address=AddressCatalog.objects.create(value="Adr split"),
            waste_type=WasteTypeCatalog.objects.create(code="990077", value="Wsplit"),
            waste_code=WasteCodeCatalog.objects.create(value="WCSPL"),
            waste_category=WasteCategoryCatalog.objects.create(value="KSPL"),
            suffix=SuffixCatalog.objects.create(value="SFXSPL"),
            drive_date=self.day,
            created_by=self.admin,
            vehicle_rz=self.rz,
            vehicle_rz_snapshot="7S77777",
            container_number="",
        )
        Pruvodka.objects.create(driver=self.driver_a, **common)
        Pruvodka.objects.create(driver=self.driver_b, **common)

    def test_two_drivers_same_rz_produce_two_ride_groups(self):
        ctx, _ = build_dashboard_rides_section(self.admin, self.day, "")
        groups = [g for g in ctx["ride_groups"] if g.get("vehicle_rz_id") == self.rz.pk]
        self.assertEqual(len(groups), 2)
        names = sorted(g["driver_last_name"] for g in groups)
        self.assertEqual(names, ["Novák", "Svoboda"])

    def test_selecting_driver_group_shows_only_their_pruvodka(self):
        key = ride_group_key(self.day, self.rz.pk, self.driver_b.pk)
        ctx, _ = build_dashboard_rides_section(self.admin, self.day, key)
        selected = ctx["selected_ride_group"]
        self.assertIsNotNone(selected)
        self.assertEqual(selected["driver_last_name"], "Svoboda")
        self.assertEqual(len(selected["items"]), 1)
        self.assertEqual(selected["items"][0].driver_id, self.driver_b.pk)

    def test_dashboard_html_shows_two_rows_same_rz(self):
        response = self.client.get(f"{reverse('core:dashboard')}?date={self.day.isoformat()}")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(html.count("7S77777"), 2)
        self.assertIn("Novák", html)
        self.assertIn("Svoboda", html)
