from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    ContainerPassport,
    IcoCatalog,
    NameCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from core.services.ride_group_ai_prompt import build_ride_group_ai_prompt
from core.services.ride_route_reorder.stop_duration_estimate import (
    estimate_stop_duration,
    format_stop_duration_for_prompt,
)
from users.constants import ROLE_ADMIN
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka


class StopDurationEstimateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("dur_admin", password="pw", is_superuser=True)
        set_user_role(self.admin, ROLE_ADMIN)
        self.day = date(2026, 6, 20)
        self.rz = VehicleRzCatalog.objects.create(value="7P88888")
        name = NameCatalog.objects.create(value="Subjekt duration")
        self.svoz_activity = ActivityCatalog.objects.create(name="Svoz", default_service_minutes=20)
        self.pristaveni = ActivityCatalog.objects.create(name="Přistavení", default_service_minutes=12)
        self.stazeni = ActivityCatalog.objects.create(name="Stažení", default_service_minutes=18)
        self.vymena = ActivityCatalog.objects.create(name="In Výměna", default_service_minutes=35)
        common = {
            "name": name,
            "ico": IcoCatalog.objects.create(value="99887766"),
            "address": AddressCatalog.objects.create(value="Adr duration"),
            "waste_type": WasteTypeCatalog.objects.create(code="880099", value="Wdur"),
            "waste_code": WasteCodeCatalog.objects.create(value="WCD"),
            "waste_category": WasteCategoryCatalog.objects.create(value="KCD"),
            "drive_date": self.day,
            "created_by": self.admin,
            "vehicle_rz": self.rz,
            "vehicle_rz_snapshot": "7P88888",
        }
        self.ride = Pruvodka.objects.create(**common)

    def test_catalog_base_minutes(self):
        Pruvodka.objects.filter(pk=self.ride.pk).update(
            activity=self.svoz_activity,
            activity_snapshot="Svoz",
        )
        self.ride.refresh_from_db()
        est = estimate_stop_duration(self.ride, {})
        self.assertEqual(est.minutes, 20)

    def test_pristaveni_ignores_rucaci_in_note(self):
        Pruvodka.objects.filter(pk=self.ride.pk).update(
            activity=self.pristaveni,
            activity_snapshot="Přistavení",
            contact_note="Ručači nakládají odpoledne",
        )
        self.ride.refresh_from_db()
        est = estimate_stop_duration(self.ride, {})
        self.assertEqual(est.minutes, 12)

    def test_stazeni_adds_manual_loading_from_note(self):
        Pruvodka.objects.filter(pk=self.ride.pk).update(
            activity=self.stazeni,
            activity_snapshot="Stažení",
            contact_note="Ručači na místě",
        )
        self.ride.refresh_from_db()
        est = estimate_stop_duration(self.ride, {})
        self.assertEqual(est.minutes, 33)
        self.assertIn("+ruční nakládka", est.modifiers)

    def test_large_container_adds_minutes(self):
        vk = VehicleKindCatalog.objects.create(name="HAK", shortcut="HAK")
        passport = ContainerPassport.objects.create(
            container_number="401",
            vehicle_kind=vk,
            color="zelená",
            volume_m3=40,
        )
        Pruvodka.objects.filter(pk=self.ride.pk).update(
            activity=self.svoz_activity,
            activity_snapshot="Svoz",
            container_number="401",
            container_passport=passport,
        )
        self.ride.refresh_from_db()
        est = estimate_stop_duration(self.ride, {"401": passport})
        self.assertEqual(est.minutes, 30)

    def test_vymena_fallback_without_catalog_fk(self):
        Pruvodka.objects.filter(pk=self.ride.pk).update(
            activity_snapshot="In Výměna",
            container_number="1",
            container_number_2="2",
        )
        self.ride.refresh_from_db()
        est = estimate_stop_duration(self.ride, {})
        self.assertEqual(est.minutes, 40)

    def test_format_duration_with_modifiers(self):
        text = format_stop_duration_for_prompt(
            estimate_stop_duration(self.ride, {})
        )
        self.assertIn("min", text)


class StopDurationPromptIntegrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("dur_prompt", password="pw", is_superuser=True)
        set_user_role(self.admin, ROLE_ADMIN)
        self.day = date(2026, 6, 21)
        name = NameCatalog.objects.create(value="Subjekt pair")
        common = {
            "name": name,
            "ico": IcoCatalog.objects.create(value="55443322"),
            "address": AddressCatalog.objects.create(value="Adr pair"),
            "waste_type": WasteTypeCatalog.objects.create(code="880100", value="Wpair"),
            "waste_code": WasteCodeCatalog.objects.create(value="WCP"),
            "waste_category": WasteCategoryCatalog.objects.create(value="KCP"),
            "drive_date": self.day,
            "created_by": self.admin,
            "vehicle_rz": VehicleRzCatalog.objects.create(value="7P99999"),
            "vehicle_rz_snapshot": "7P99999",
        }
        self.pristaveni = Pruvodka.objects.create(
            **common,
            activity_snapshot="Přistavení",
            name_snapshot="Subjekt pair",
        )
        self.stazeni = Pruvodka.objects.create(
            **common,
            activity_snapshot="Stažení",
            name_snapshot="Subjekt pair",
            follow_up_parent=self.pristaveni,
        )

    def test_prompt_has_duration_and_follow_up_columns(self):
        prompt = build_ride_group_ai_prompt(
            drive_date=self.day,
            vehicle_rz="7P99999",
            driver_label="—",
            items=[self.pristaveni, self.stazeni],
        )
        self.assertIn("odhad min", prompt)
        self.assertIn("návaznost", prompt)
        self.assertIn("Páry přistavení → stažení", prompt)
        self.assertIn(f"pk {self.pristaveni.pk}", prompt)
        self.assertIn(f"navazuje na pk {self.pristaveni.pk}", prompt)
        self.assertIn("Odhad délky zastávky", prompt)
        self.assertIn("přistavení vždy před stažením", prompt)
