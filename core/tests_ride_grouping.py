"""Testy klíčů skupin jízd na dashboardu."""

from __future__ import annotations

from datetime import date

from django.test import SimpleTestCase

from core.services.ride_grouping import (
    parse_ride_group_key,
    plan_only_ride_group_key,
    resolve_ride_group,
    ride_group_key,
)


class RideGroupingKeyTests(SimpleTestCase):
    def test_ride_group_key_includes_driver(self):
        d = date(2026, 6, 12)
        self.assertEqual(ride_group_key(d, 5, 10), "2026-06-12::5::10")
        self.assertEqual(ride_group_key(d, None, None), "2026-06-12::0::0")

    def test_plan_only_key_suffix(self):
        d = date(2026, 6, 12)
        self.assertEqual(plan_only_ride_group_key(d, 5, 10), "2026-06-12::5::10::plan")

    def test_parse_ride_group_key(self):
        d, rz, drv, is_plan = parse_ride_group_key("2026-06-12::5::10::plan")
        self.assertEqual(d, date(2026, 6, 12))
        self.assertEqual(rz, 5)
        self.assertEqual(drv, 10)
        self.assertTrue(is_plan)

    def test_resolve_legacy_key_without_driver(self):
        groups = [
            {
                "key": "2026-06-12::5::10",
                "drive_date": date(2026, 6, 12),
                "vehicle_rz_id": 5,
                "driver_id": 10,
                "is_plan_only": False,
            },
            {
                "key": "2026-06-12::5::20",
                "drive_date": date(2026, 6, 12),
                "vehicle_rz_id": 5,
                "driver_id": 20,
                "is_plan_only": False,
            },
        ]
        resolved = resolve_ride_group(groups, "2026-06-12::5")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["driver_id"], 10)

    def test_resolve_exact_key(self):
        groups = [
            {
                "key": "2026-06-12::5::20",
                "drive_date": date(2026, 6, 12),
                "vehicle_rz_id": 5,
                "driver_id": 20,
            },
        ]
        resolved = resolve_ride_group(groups, "2026-06-12::5::20")
        self.assertEqual(resolved["driver_id"], 20)
