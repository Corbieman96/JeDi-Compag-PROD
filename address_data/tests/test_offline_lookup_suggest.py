"""Našeptávač adres z offline DB (addresses.sqlite3) + RÚIAN fallback."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from address_data.models import OfflineAddress
from address_data.services.offline_lookup import geocode_address, reverse_geocode, suggest_addresses
from address_data.services.query_variants import build_query_variants
from address_data.services.ruian_geocoding import ruian_text_to_strict_label


ROSTKOV_ROW = {
    "city": "Chocnějovice",
    "street": "Rostkov",
    "house_number": "1",
    "postal_code": "29413",
    "label": "Rostkov, 1, Chocnějovice",
    "lat": 50.58835927935388,
    "lng": 14.947273986132277,
}

ROSTKOV_SUGGEST = [
    {
        "text": "Rostkov 1, 29413 Chocnějovice",
        "label": "Rostkov, 1, Chocnějovice",
        "magicKey": "1_418413",
        "type": "AdresniMisto",
    }
]


class OfflineLookupSuggestTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        OfflineAddress.objects.create(
            city="Kolomuty",
            street="Kolomuty",
            house_number="100",
            postal_code="29443",
            label="Kolomuty, 100, Kolomuty",
            lat=Decimal("50.2000000"),
            lng=Decimal("14.9000000"),
            city_norm="kolomuty",
            street_norm="kolomuty",
            label_norm="kolomuty, 100, kolomuty",
        )
        OfflineAddress.objects.create(
            city="Liberec",
            street="Masarykova",
            house_number="726/29",
            postal_code="46001",
            label="Masarykova, 726/29, Liberec",
            lat=Decimal("50.7700000"),
            lng=Decimal("15.0500000"),
            city_norm="liberec",
            street_norm="masarykova",
            label_norm="masarykova, 726/29, liberec",
        )

    def test_suggest_returns_fulfillment_format_village(self):
        results = suggest_addresses("Kolomuty", limit=5)
        self.assertTrue(any("Kolomuty, 100, Kolomuty" in row for row in results))

    def test_suggest_returns_fulfillment_format_street(self):
        results = suggest_addresses("Masarykova", limit=5)
        self.assertTrue(any("Masarykova, 726/29, Liberec" in row for row in results))

    def test_suggest_single_char_returns_empty(self):
        self.assertEqual(suggest_addresses("K"), [])

    @patch("address_data.services.offline_lookup.ruian_find", return_value=ROSTKOV_ROW)
    @patch("address_data.services.offline_lookup.ruian_suggest_addresses", return_value=ROSTKOV_SUGGEST)
    def test_suggest_ruian_fallback_rostkov(self, _suggest_mock, _find_mock):
        results = suggest_addresses("Rostkov, 1, Mohelnice nad Jizerou", limit=5)
        self.assertIn("Rostkov, 1, Chocnějovice", results)

    @patch("address_data.services.offline_lookup.ruian_geocode_single_line", return_value=ROSTKOV_ROW)
    def test_geocode_ruian_fallback(self, _mock):
        hit = geocode_address("Rostkov, 1, Mohelnice nad Jizerou")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["label"], "Rostkov, 1, Chocnějovice")
        self.assertAlmostEqual(hit["lat"], ROSTKOV_ROW["lat"], places=5)

    @patch("address_data.services.offline_lookup.reverse_geocode_czech_with_payload", return_value=(None, None))
    @patch("address_data.services.offline_lookup.ruian_reverse_geocode", return_value=ROSTKOV_ROW)
    def test_reverse_geocode_ruian_first(self, _mock_ruian, _mock_osm):
        with patch("address_data.services.offline_lookup.upsert_offline_rows"):
            hit = reverse_geocode(lat=ROSTKOV_ROW["lat"], lng=ROSTKOV_ROW["lng"])
        self.assertEqual(hit["label"], "Rostkov, 1, Chocnějovice")


class QueryVariantsTests(TestCase):
    def test_strict_format_generates_street_number_variant(self):
        variants = build_query_variants("Rostkov, 1, Mohelnice nad Jizerou")
        self.assertIn("Rostkov 1", variants)

    def test_ruian_attrs_to_row_praha_format(self):
        from address_data.services.ruian_geocoding import ruian_attrs_to_row

        row = ruian_attrs_to_row(
            {
                "adresa": "Korunní 586/2, Vinohrady, 12000 Praha 2",
                "psc": 12000,
                "cislodomovni": 586,
                "cisloorientacni": 2,
                "cisloorientacnipismeno": None,
            },
            lat=50.075,
            lng=14.437,
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["city"], "Praha 2")
        self.assertEqual(row["street"], "Korunní")
        self.assertEqual(row["house_number"], "586/2")
        self.assertEqual(row["label"], "Korunní, 586/2, Praha 2")

    def test_ruian_attrs_to_row_accepts_int_psc(self):
        from address_data.services.ruian_geocoding import ruian_attrs_to_row

        row = ruian_attrs_to_row(
            {
                "adresa": "Rostkov 1, 29413 Chocnějovice",
                "psc": 29413,
                "cislodomovni": 1,
                "cisloorientacni": None,
                "cisloorientacnipismeno": None,
            },
            lat=50.588,
            lng=14.947,
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["postal_code"], "29413")
        self.assertEqual(row["label"], "Rostkov, 1, Chocnějovice")


class NameAddressSuggestionsViewTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username="addr_suggest_admin", password="x", is_superuser=True)
        OfflineAddress.objects.create(
            city="Kolomuty",
            street="Kolomuty",
            house_number="123",
            postal_code="29443",
            label="Kolomuty, 123, Kolomuty",
            lat=Decimal("50.2000000"),
            lng=Decimal("14.9000000"),
            city_norm="kolomuty",
            street_norm="kolomuty",
            label_norm="kolomuty, 123, kolomuty",
        )

    def test_address_suggestions_view_returns_json(self):
        client = Client()
        client.force_login(self.admin)
        url = reverse("catalogs:name_address_suggestions")
        response = client.get(url, {"q": "Kolom"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("ok"))
        self.assertTrue(any("Kolomuty" in row for row in payload.get("data", [])))

    def test_address_suggestions_view_requires_min_length(self):
        client = Client()
        client.force_login(self.admin)
        url = reverse("catalogs:name_address_suggestions")
        response = client.get(url, {"q": "Ko"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("data"), [])

    @patch("address_data.services.offline_lookup.ruian_find", return_value=ROSTKOV_ROW)
    @patch("address_data.services.offline_lookup.ruian_suggest_addresses", return_value=ROSTKOV_SUGGEST)
    def test_address_suggestions_view_ruian_fallback(self, _suggest_mock, _find_mock):
        client = Client()
        client.force_login(self.admin)
        url = reverse("catalogs:name_address_suggestions")
        response = client.get(url, {"q": "Rostkov, 1, Mohelnice"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any("Rostkov, 1, Chocnějovice" in row for row in payload.get("data", [])))
