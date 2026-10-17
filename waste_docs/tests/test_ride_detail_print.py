from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
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
from users.constants import ROLE_ADMIN
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka
from waste_docs.services.ride_detail_print import (
    build_detail_print_context,
    build_detail_print_file_rows,
    peers_for_ride_group,
    protocol_group_pdf_url,
)


class RideDetailPrintTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("detail_print_user", password="pw", is_superuser=True)
        set_user_role(self.user, ROLE_ADMIN)
        self.drive_date = date(2026, 7, 1)
        self.rz = VehicleRzCatalog.objects.create(value="1A11111")
        self.driver_a = DriverProfile.objects.create(
            first_name="Jan",
            last_name="Hlaváček",
            personal_number="1001",
        )
        self.driver_b = DriverProfile.objects.create(
            first_name="Petr",
            last_name="Novák",
            personal_number="1002",
        )
        common = dict(
            name=NameCatalog.objects.create(value="Subjekt detail print"),
            ico=IcoCatalog.objects.create(value="12345678"),
            address=AddressCatalog.objects.create(value="Adr detail print"),
            waste_type=WasteTypeCatalog.objects.create(code="990099", value="Wdp"),
            waste_code=WasteCodeCatalog.objects.create(value="WCDP"),
            waste_category=WasteCategoryCatalog.objects.create(value="KODP"),
            suffix=SuffixCatalog.objects.create(value="SFXDP"),
            drive_date=self.drive_date,
            vehicle_rz=self.rz,
            vehicle_rz_snapshot="1A11111",
            created_by=self.user,
            container_number="",
        )
        self.ride_a = Pruvodka.objects.create(
            driver=self.driver_a,
            driver_snapshot="Hlaváček Jan",
            ride_group_number=10,
            ride_sequence=1,
            created_at=datetime(2026, 7, 1, 8, 0, tzinfo=dt_timezone.utc),
            **common,
        )
        self.ride_b = Pruvodka.objects.create(
            driver=self.driver_a,
            driver_snapshot="Hlaváček Jan",
            ride_group_number=10,
            ride_sequence=2,
            created_at=datetime(2026, 7, 1, 9, 0, tzinfo=dt_timezone.utc),
            **common,
        )
        self.ride_other_driver = Pruvodka.objects.create(
            driver=self.driver_b,
            driver_snapshot="Novák Petr",
            ride_group_number=10,
            ride_sequence=1,
            created_at=datetime(2026, 7, 1, 10, 0, tzinfo=dt_timezone.utc),
            **common,
        )

    def test_peers_for_ride_group_respects_driver(self):
        peers = peers_for_ride_group(self.ride_a, self.user)
        self.assertEqual({r.pk for r in peers}, {self.ride_a.pk, self.ride_b.pk})
        self.assertNotIn(self.ride_other_driver.pk, {r.pk for r in peers})

    def test_build_detail_print_context_shows_group_protocol(self):
        ctx = build_detail_print_context(self.ride_a, self.user)
        self.assertTrue(ctx["show_group_protocol"])
        self.assertEqual(ctx["group_peer_count"], 2)
        self.assertIn("driver_id=", protocol_group_pdf_url(self.ride_a))

    def test_build_detail_print_file_rows_contains_pdf_urls(self):
        rows = build_detail_print_file_rows(self.ride_a, self.user)
        kinds = {row["kind"] for row in rows}
        self.assertIn("pruvodka", kinds)
        self.assertIn("protocol_single", kinds)
        self.assertIn("protocol_group", kinds)
        for row in rows:
            self.assertTrue(row["print_url"].startswith("/"))

    def test_detail_page_shows_tisk_pdf_button(self):
        from django.test import Client

        client = Client()
        client.force_login(self.user)
        response = client.get(reverse("waste_docs:detail", kwargs={"pk": self.ride_a.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tisk (PDF)")
        self.assertContains(response, "Co vytisknout")
        self.assertNotContains(response, "jizda.xlsx")
