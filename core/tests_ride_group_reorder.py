from __future__ import annotations

import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    AddressCatalog,
    ContainerPassport,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from core.services.ride_group_ai_prompt import build_ride_group_ai_prompt
from core.services.ride_group_reorder import reorder_ride_group_items
from core.services.ride_grouping import ride_group_key
from users.constants import ROLE_ADMIN
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka
from waste_docs.services.ride_print_order import sort_rides_list


class RideGroupReorderTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("reorder_admin", password="pw", is_superuser=True)
        set_user_role(self.admin, ROLE_ADMIN)
        self.day = date(2026, 6, 15)
        self.rz = VehicleRzCatalog.objects.create(value="7P77777")
        self.driver = DriverProfile.objects.create(personal_number="RO-1", last_name="Novák")
        name = NameCatalog.objects.create(value="Subjekt reorder")
        common = {
            "name": name,
            "ico": IcoCatalog.objects.create(value="11223344"),
            "address": AddressCatalog.objects.create(value="Adr reorder"),
            "waste_type": WasteTypeCatalog.objects.create(code="880088", value="Wreorder"),
            "waste_code": WasteCodeCatalog.objects.create(value="WCR"),
            "waste_category": WasteCategoryCatalog.objects.create(value="KCR"),
            "drive_date": self.day,
            "created_by": self.admin,
            "vehicle_rz": self.rz,
            "vehicle_rz_snapshot": "7P77777",
            "driver": self.driver,
            "driver_snapshot": "Novák",
        }
        self.ride_a = Pruvodka.objects.create(**common)
        self.ride_b = Pruvodka.objects.create(**common)
        self.ride_c = Pruvodka.objects.create(**common)
        Pruvodka.objects.filter(pk=self.ride_a.pk).update(
            ride_group_number=666,
            ride_sequence=1,
            snd_cislo_listu="0000666-2026-1",
        )
        Pruvodka.objects.filter(pk=self.ride_b.pk).update(
            ride_group_number=666,
            ride_sequence=2,
            snd_cislo_listu="0000666-2026-2",
        )
        Pruvodka.objects.filter(pk=self.ride_c.pk).update(
            ride_group_number=555,
            ride_sequence=3,
            snd_cislo_listu="0000555-2026-3",
        )
        self.ride_a.refresh_from_db()
        self.ride_b.refresh_from_db()
        self.ride_c.refresh_from_db()
        self.group_key = ride_group_key(self.day, self.rz.pk, self.driver.pk)

    def test_reorder_sets_route_order_without_changing_snd(self):
        changed, warnings = reorder_ride_group_items(
            drive_date=self.day,
            vehicle_rz_id=self.rz.pk,
            driver_id=self.driver.pk,
            ordered_pks=[self.ride_c.pk, self.ride_a.pk, self.ride_b.pk],
        )
        self.assertEqual(changed, 3)
        self.assertTrue(any("smíchaná" in w.lower() for w in warnings))

        self.ride_a.refresh_from_db()
        self.ride_b.refresh_from_db()
        self.ride_c.refresh_from_db()

        self.assertEqual(self.ride_c.ride_route_order, 1)
        self.assertEqual(self.ride_a.ride_route_order, 2)
        self.assertEqual(self.ride_b.ride_route_order, 3)

        self.assertEqual(self.ride_a.snd_cislo_listu, "0000666-2026-1")
        self.assertEqual(self.ride_b.snd_cislo_listu, "0000666-2026-2")
        self.assertEqual(self.ride_c.snd_cislo_listu, "0000555-2026-3")
        self.assertEqual(self.ride_a.ride_sequence, 1)
        self.assertEqual(self.ride_c.ride_sequence, 3)

    def test_sort_rides_list_prefers_route_order(self):
        self.ride_b.ride_route_order = 1
        self.ride_a.ride_route_order = 2
        ordered = sort_rides_list([self.ride_a, self.ride_b, self.ride_c])
        self.assertEqual([r.pk for r in ordered], [self.ride_b.pk, self.ride_a.pk, self.ride_c.pk])

    def test_post_reorder_api(self):
        self.client.force_login(self.admin)
        url = reverse("core:ride_group_reorder")
        resp = self.client.post(
            url + f"?date={self.day.isoformat()}&ride_group={self.group_key}",
            data=json.dumps({"order": [self.ride_b.pk, self.ride_a.pk, self.ride_c.pk]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])

        self.ride_a.refresh_from_db()
        self.assertEqual(self.ride_a.ride_route_order, 2)

    def test_post_reorder_invalid_pk(self):
        self.client.force_login(self.admin)
        url = reverse("core:ride_group_reorder")
        resp = self.client.post(
            url + f"?date={self.day.isoformat()}&ride_group={self.group_key}",
            data=json.dumps({"order": [self.ride_a.pk, 99999]}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_ai_prompt_contains_pk_and_snd(self):
        prompt = build_ride_group_ai_prompt(
            drive_date=self.day,
            vehicle_rz="7P77777",
            driver_label="Novák",
            items=[self.ride_a, self.ride_b, self.ride_c],
        )
        self.assertIn(str(self.ride_a.pk), prompt)
        self.assertIn("0000666-2026-1", prompt)
        self.assertIn("Navrhni optimální pořadí", prompt)

    def test_ai_prompt_contains_domain_glossary(self):
        prompt = build_ride_group_ai_prompt(
            drive_date=self.day,
            vehicle_rz="7P77777",
            driver_label="Novák",
            items=[self.ride_a, self.ride_b, self.ride_c],
        )
        self.assertIn("Důležité pojmy", prompt)
        self.assertIn("Pravidla řazení", prompt)
        self.assertIn("Výstupní formát", prompt)
        self.assertIn("Výměna", prompt)
        self.assertIn("COMPAG MLADÁ BOLESLAV", prompt)
        self.assertIn("Přistavit a Stáhnout", prompt)
        self.assertIn("Vstupní data", prompt)

    def test_ai_prompt_includes_contact_note(self):
        Pruvodka.objects.filter(pk=self.ride_a.pk).update(
            contact_note="Přistavení do 8:00, stažení od 14:00",
        )
        self.ride_a.refresh_from_db()
        prompt = build_ride_group_ai_prompt(
            drive_date=self.day,
            vehicle_rz="7P77777",
            driver_label="Novák",
            items=[self.ride_a],
        )
        self.assertIn("Přistavení do 8:00", prompt)
        self.assertIn("poznámka", prompt.lower())

    def test_ai_prompt_describes_exchange_activity(self):
        Pruvodka.objects.filter(pk=self.ride_a.pk).update(
            activity_snapshot="In Výměna",
            container_number="259",
            container_number_2="253",
        )
        self.ride_a.refresh_from_db()
        prompt = build_ride_group_ai_prompt(
            drive_date=self.day,
            vehicle_rz="7P77777",
            driver_label="Novák",
            items=[self.ride_a],
        )
        self.assertIn("In Výměna = výměna VOK na místě", prompt)
        self.assertIn("259", prompt)
        self.assertIn("253", prompt)

    def test_ai_prompt_container_passport_volume(self):
        vk = VehicleKindCatalog.objects.create(name="HAK", shortcut="HAK")
        passport = ContainerPassport.objects.create(
            container_number="259",
            vehicle_kind=vk,
            color="zelená",
            volume_m3=40,
        )
        Pruvodka.objects.filter(pk=self.ride_a.pk).update(
            container_number="259",
            container_passport=passport,
        )
        self.ride_a.refresh_from_db()
        prompt = build_ride_group_ai_prompt(
            drive_date=self.day,
            vehicle_rz="7P77777",
            driver_label="Novák",
            items=[self.ride_a],
        )
        self.assertIn("259 VOK 40 m³", prompt)
        self.assertIn("druh vozidla: HAK", prompt)
        self.assertIn("30 min", prompt)

    def test_ai_prompt_duration_columns_in_header(self):
        prompt = build_ride_group_ai_prompt(
            drive_date=self.day,
            vehicle_rz="7P77777",
            driver_label="Novák",
            items=[self.ride_a],
        )
        self.assertIn("odhad min", prompt)
        self.assertIn("návaznost", prompt)

    def test_ai_prompt_api(self):
        self.client.force_login(self.admin)
        url = reverse("core:ride_group_ai_prompt")
        resp = self.client.get(url + f"?date={self.day.isoformat()}&ride_group={self.group_key}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["mixed_snd_groups"])

    def test_ai_prompt_api_double_encoded_ride_group(self):
        self.client.force_login(self.admin)
        url = reverse("core:ride_group_ai_prompt")
        double_encoded = self.group_key.replace(":", "%253A")
        resp = self.client.get(
            url + f"?date={self.day.isoformat()}&ride_group={double_encoded}"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

    def test_reorder_ui_only_in_modal_not_panel(self):
        self.client.force_login(self.admin)
        url = (
            f"{reverse('core:dashboard')}?date={self.day.isoformat()}"
            f"&ride_group={self.group_key}"
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        panel_start = html.index("dash-panel--ride-detail")
        panel_end = html.index("</section>", panel_start)
        panel_html = html[panel_start:panel_end]
        modal_start = html.index("dash-ride-detail-modal")
        modal_end = html.index('id="dash-ride-email-modal"', modal_start)
        modal_html = html[modal_start:modal_end]

        self.assertNotIn("Uspořádat zastávky", panel_html)
        self.assertNotIn("Prompt pro AI", panel_html)
        self.assertNotIn("dash-ride-reorder-root", panel_html)
        self.assertNotIn("Poř.", panel_html)

        self.assertIn("Uspořádat zastávky", modal_html)
        self.assertIn("Prompt pro AI", modal_html)
        self.assertIn("Navrhnout pořadí", modal_html)
        self.assertIn("dash-ride-reorder-root", modal_html)
        self.assertIn("Poř.", modal_html)
        self.assertIn("dash-ride-reorder-up", modal_html)
        self.assertIn('data-reorder-js-version="7"', modal_html)
