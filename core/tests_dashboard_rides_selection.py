from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from users.constants import ROLE_ADMIN
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka
from core.services.ride_grouping import ride_group_key


class DashboardRideSelectionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("dash_sel_admin", password="pw", is_superuser=True)
        set_user_role(self.admin, ROLE_ADMIN)
        self.day = date(2026, 6, 12)
        name = NameCatalog.objects.create(value="Subjekt dash sel")
        common = {
            "name": name,
            "ico": IcoCatalog.objects.create(value="99887766"),
            "address": AddressCatalog.objects.create(value="Adr dash sel"),
            "waste_type": WasteTypeCatalog.objects.create(code="990098", value="Wsel"),
            "waste_code": WasteCodeCatalog.objects.create(value="WCSEL"),
            "waste_category": WasteCategoryCatalog.objects.create(value="KCSEL"),
            "drive_date": self.day,
            "created_by": self.admin,
        }
        rz_a = VehicleRzCatalog.objects.create(value="1A11111")
        rz_b = VehicleRzCatalog.objects.create(value="1B22222")
        self.ride_a = Pruvodka.objects.create(vehicle_rz=rz_a, vehicle_rz_snapshot="1A11111", **common)
        self.ride_b = Pruvodka.objects.create(vehicle_rz=rz_b, vehicle_rz_snapshot="1B22222", **common)
        self.group_a_key = ride_group_key(self.day, rz_a.pk, None)

    def _dashboard(self, query: str = ""):
        url = f"{reverse('core:dashboard')}?date={self.day.isoformat()}{query}"
        self.client.force_login(self.admin)
        return self.client.get(url)

    def test_without_ride_group_detail_is_empty_and_bulk_print(self):
        response = self._dashboard()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vyberte jízdu v seznamu vlevo")
        self.assertIsNone(response.context.get("selected_ride_group"))
        self.assertFalse(response.context.get("ride_group_explicit"))
        self.assertIn("dashboard-bulk", response.context["dashboard_header_print_url"])

    def test_with_valid_ride_group_shows_detail(self):
        response = self._dashboard(f"&ride_group={self.group_a_key}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1A11111")
        self.assertContains(response, 'aria-label="Zrušit výběr jízdy"')
        self.assertContains(response, "dash-panel__icon-btn--clear-select")
        self.assertContains(response, "dash-icon-stroke")
        self.assertEqual(response.content.count(b"dash-panel__icon-btn--clear-select"), 2)
        self.assertTrue(response.context.get("ride_group_explicit"))
        self.assertIn("ride-bundle", response.context["dashboard_header_print_url"])
        self.assertIn(f"vehicle_rz_id={self.ride_a.vehicle_rz_id}", response.context["dashboard_header_print_url"])
        clear_url = response.context["dashboard_clear_ride_selection_url"]
        self.assertIn(f"date={self.day.isoformat()}", clear_url)
        self.assertNotIn("ride_group", clear_url)

    def test_clear_selection_url_resets_ride_group(self):
        clear_url = f"{reverse('core:dashboard')}?date={self.day.isoformat()}"
        self.client.force_login(self.admin)
        response = self.client.get(clear_url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context.get("selected_ride_group"))
        self.assertFalse(response.context.get("ride_group_explicit"))
        self.assertContains(response, "Vyberte jízdu v seznamu vlevo")

    def test_stale_ride_group_treated_as_no_selection(self):
        stale = f"2099-01-01::{self.ride_a.vehicle_rz_id}"
        response = self._dashboard(f"&ride_group={stale}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vyberte jízdu v seznamu vlevo")
        self.assertIsNone(response.context.get("selected_ride_group"))
        self.assertFalse(response.context.get("ride_group_explicit"))
        self.assertIn("dashboard-bulk", response.context["dashboard_header_print_url"])
