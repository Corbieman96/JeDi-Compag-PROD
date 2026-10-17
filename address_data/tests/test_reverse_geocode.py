"""Testy reverse geocoding — vzdálenost, merge OSM + RÚIAN."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from address_data.models import OfflineAddress
from address_data.services.geo_distance import REVERSE_MAX_DISTANCE_M, haversine_m
from address_data.services.offline_lookup import _reverse_geocode_offline, reverse_geocode
from address_data.services.osm_building_at_point import building_ref_at_point, point_in_polygon
from address_data.services.reverse_merge import merge_map_pin_label, osm_building_ref
from address_data.services.ruian_geocoding import ruian_reverse_geocode


class HaversineTests(TestCase):
    def test_haversine_same_point_is_zero(self):
        self.assertAlmostEqual(haversine_m(50.0, 15.0, 50.0, 15.0), 0.0, places=3)

    def test_haversine_degree_hypot_would_be_wrong(self):
        """Stupňová euklidovská vzdálenost není spolehlivá pro výběr adresy."""
        lat1, lng1 = 50.4136, 14.9084
        lat2, lng2 = 50.4140, 14.9084
        dist_m = haversine_m(lat1, lng1, lat2, lng2)
        self.assertGreater(dist_m, 30)


class ReverseMergeTests(TestCase):
    def test_osm_building_ref_from_name(self):
        payload = {"name": "M6", "address": {"road": "třída Jičínská", "city": "Mladá Boleslav"}}
        self.assertEqual(osm_building_ref(payload), "M6")

    def test_merge_ruian_with_building_ref(self):
        ruian = {
            "city": "Mladá Boleslav",
            "street": "třída Jičínská",
            "house_number": "1349",
            "label": "třída Jičínská, 1349, Mladá Boleslav",
        }
        nominatim = {"name": "M6", "address": {"road": "třída Jičínská"}}
        label = merge_map_pin_label(nominatim_payload=nominatim, ruian_row=ruian)
        self.assertEqual(label, "třída Jičínská, M6, Mladá Boleslav")

    def test_merge_prefers_overpass_building_ref_over_nominatim(self):
        ruian = {
            "city": "Mladá Boleslav",
            "street": "třída Václava Klementa",
            "house_number": "1349",
            "label": "třída Václava Klementa, 1349, Mladá Boleslav",
        }
        nominatim = {"name": "M2", "address": {"road": "třída Václava Klementa"}}
        label = merge_map_pin_label(
            nominatim_payload=nominatim,
            ruian_row=ruian,
            building_ref="M6",
        )
        self.assertEqual(label, "třída Václava Klementa, M6, Mladá Boleslav")

    def test_merge_osm_only_with_ref(self):
        osm = {
            "city": "Mladá Boleslav",
            "street": "třída Jičínská",
            "house_number": "",
        }
        nominatim = {"name": "M6", "address": {"road": "třída Jičínská", "city": "Mladá Boleslav"}}
        label = merge_map_pin_label(nominatim_payload=nominatim, osm_row=osm)
        self.assertEqual(label, "třída Jičínská, M6, Mladá Boleslav")


class RuianReverseDistanceTests(TestCase):
    def test_ruian_reverse_rejects_far_feature(self):
        pin_lat, pin_lng = 50.4136, 14.9084
        near_lat, near_lng = pin_lat + 0.00001, pin_lng + 0.00001
        far_lat, far_lng = pin_lat + 0.001, pin_lng + 0.001

        features = {
            "features": [
                {
                    "attributes": {
                        "adresa": "třída Jičínská 1349, 29301 Mladá Boleslav",
                        "psc": 29301,
                        "cislodomovni": 1349,
                    },
                    "geometry": {"x": near_lng, "y": near_lat},
                },
                {
                    "attributes": {
                        "adresa": "Jiná ulice 1, 29301 Mladá Boleslav",
                        "psc": 29301,
                        "cislodomovni": 1,
                    },
                    "geometry": {"x": far_lng, "y": far_lat},
                },
            ]
        }

        with patch("address_data.services.ruian_geocoding._fetch_json", return_value=features):
            hit = ruian_reverse_geocode(pin_lat, pin_lng)
        self.assertIsNotNone(hit)
        self.assertIn("1349", hit["house_number"])

        far_pin_lat, far_pin_lng = pin_lat + 0.005, pin_lng + 0.005
        with patch("address_data.services.ruian_geocoding._fetch_json", return_value=features):
            hit_far = ruian_reverse_geocode(far_pin_lat, far_pin_lng)
        if hit_far:
            dist = haversine_m(far_pin_lat, far_pin_lng, hit_far["lat"], hit_far["lng"])
            self.assertLessEqual(dist, REVERSE_MAX_DISTANCE_M)


class OfflineReverseDistanceTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        OfflineAddress.objects.create(
            city="Mladá Boleslav",
            street="třída Jičínská",
            house_number="1349",
            postal_code="29301",
            label="třída Jičínská, 1349, Mladá Boleslav",
            lat=Decimal("50.4136000"),
            lng=Decimal("14.9084000"),
            city_norm="mlada boleslav",
            street_norm="trida jicinska",
            label_norm="trida jicinska, 1349, mlada boleslav",
        )

    def test_offline_reverse_within_range(self):
        hit = _reverse_geocode_offline(50.41361, 14.90841)
        self.assertIsNotNone(hit)
        self.assertIn("1349", hit["label"])

    def test_offline_reverse_rejects_far_point(self):
        hit = _reverse_geocode_offline(50.4200, 14.9200)
        self.assertIsNone(hit)


class PointInPolygonTests(TestCase):
    def test_point_inside_square(self):
        ring = [
            (50.0, 14.0),
            (50.0, 14.001),
            (50.001, 14.001),
            (50.001, 14.0),
        ]
        self.assertTrue(point_in_polygon(50.0005, 14.0005, ring))
        self.assertFalse(point_in_polygon(50.002, 14.0005, ring))


class BuildingAtPointTests(TestCase):
    def _overpass_payload(self, m2_ring, m6_ring):
        return {
            "elements": [
                {
                    "type": "way",
                    "tags": {"building": "industrial", "name": "M2"},
                    "geometry": [{"lat": lat, "lon": lng} for lat, lng in m2_ring],
                },
                {
                    "type": "way",
                    "tags": {"building": "industrial", "name": "M6"},
                    "geometry": [{"lat": lat, "lon": lng} for lat, lng in m6_ring],
                },
            ]
        }

    def test_building_ref_at_point_prefers_containing_polygon(self):
        m2_ring = [
            (50.4100, 14.9180),
            (50.4100, 14.9184),
            (50.4104, 14.9184),
            (50.4104, 14.9180),
        ]
        m6_ring = [
            (50.4104, 14.9180),
            (50.4104, 14.9184),
            (50.4108, 14.9184),
            (50.4108, 14.9180),
        ]
        payload = self._overpass_payload(m2_ring, m6_ring)
        with patch("address_data.services.osm_building_at_point.load_overpass_json", return_value=payload):
            ref = building_ref_at_point(50.4106, 14.9182)
        self.assertEqual(ref, "M6")

    def test_building_ref_at_point_empty_when_no_match(self):
        with patch("address_data.services.osm_building_at_point.load_overpass_json", return_value={"elements": []}):
            ref = building_ref_at_point(50.4106, 14.9182)
        self.assertEqual(ref, "")


class ReverseGeocodeIntegrationTests(TestCase):
    databases = {"default", "addresses"}

    @patch("address_data.services.offline_lookup.reverse_geocode_czech_with_payload")
    @patch("address_data.services.offline_lookup.ruian_reverse_geocode")
    def test_reverse_geocode_merges_skoda_m6(self, mock_ruian, mock_osm):
        mock_ruian.return_value = {
            "city": "Mladá Boleslav",
            "street": "třída Jičínská",
            "house_number": "1349",
            "label": "třída Jičínská, 1349, Mladá Boleslav",
            "lat": 50.4136,
            "lng": 14.9084,
        }
        mock_osm.return_value = (
            {
                "city": "Mladá Boleslav",
                "street": "třída Jičínská",
                "house_number": "",
                "label": "třída Jičínská, Mladá Boleslav",
            },
            {"name": "M6", "address": {"road": "třída Jičínská", "city": "Mladá Boleslav"}},
        )
        with patch("address_data.services.offline_lookup.upsert_offline_rows"):
            hit = reverse_geocode(lat=50.4137, lng=14.9085)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["label"], "třída Jičínská, M6, Mladá Boleslav")

    @patch("address_data.services.offline_lookup.building_ref_at_point", return_value="M6")
    @patch("address_data.services.offline_lookup.reverse_geocode_czech_with_payload")
    @patch("address_data.services.offline_lookup.ruian_reverse_geocode")
    def test_reverse_geocode_uses_overpass_instead_of_wrong_nominatim(self, mock_ruian, mock_osm, _mock_overpass):
        mock_ruian.return_value = {
            "city": "Mladá Boleslav",
            "street": "třída Václava Klementa",
            "house_number": "1349",
            "label": "třída Václava Klementa, 1349, Mladá Boleslav",
            "lat": 50.4106,
            "lng": 14.9182,
        }
        mock_osm.return_value = (
            {
                "city": "Mladá Boleslav",
                "street": "třída Václava Klementa",
                "house_number": "",
                "label": "třída Václava Klementa, Mladá Boleslav",
            },
            {"name": "M2", "address": {"road": "třída Václava Klementa", "city": "Mladá Boleslav"}},
        )
        with patch("address_data.services.offline_lookup.upsert_offline_rows"):
            hit = reverse_geocode(lat=50.4106, lng=14.9182)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["label"], "třída Václava Klementa, M6, Mladá Boleslav")
