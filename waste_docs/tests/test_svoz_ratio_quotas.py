"""Celočíselné kvóty poměru B1:B2 v plánu svozů."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from waste_docs.services.svoz_dispatch.ratio_quotas import (
    effective_integer_quotas,
    effective_ratio_hint,
    effective_ratio_label,
    parse_ratio_parts,
    validate_ratio_for_slots,
    weights_for_ratio,
)
from waste_docs.services.svoz_dispatch.weighted_assignment import pick_weighted_assignment


class SvozRatioQuotasTests(TestCase):
    def test_two_one_with_two_containers_becomes_one_one(self):
        quotas = effective_integer_quotas([2, 1], 2)
        self.assertEqual(quotas, [1, 1])
        self.assertEqual(effective_ratio_label([2, 1], 2), "1:1")

    def test_two_one_with_one_container_goes_to_higher_weight(self):
        quotas = effective_integer_quotas([2, 1], 1)
        self.assertEqual(quotas, [1, 0])

    def test_one_three_with_one_container_goes_to_b2(self):
        quotas = effective_integer_quotas([1, 3], 1)
        self.assertEqual(quotas, [0, 1])

    def test_two_one_with_three_containers_stays_two_one(self):
        quotas = effective_integer_quotas([2, 1], 3)
        self.assertEqual(quotas, [2, 1])

    def test_effective_ratio_hint_shows_source_ratio_when_rounded(self):
        hint = effective_ratio_hint([2, 1], 2, "2:1")
        self.assertIn("1 : 1", hint)
        self.assertIn("2 : 1", hint)

    def test_simulated_assignment_matches_quotas_for_two_one(self):
        rows = [
            SimpleNamespace(driver_id=10, vehicle_rz_id=1, sort_order=0, assignment_weight=2),
            SimpleNamespace(driver_id=20, vehicle_rz_id=2, sort_order=1, assignment_weight=1),
        ]
        counts: dict[tuple[int | None, int | None], int] = {}
        assigned: dict[int, int] = {10: 0, 20: 0}
        for _ in range(3):
            driver_id, rz_id = pick_weighted_assignment(rows, counts)
            key = (driver_id, rz_id)
            counts[key] = counts.get(key, 0) + 1
            assigned[int(driver_id)] += 1
        self.assertEqual(assigned[10], 2)
        self.assertEqual(assigned[20], 1)

    def test_parse_ratio_three_parts(self):
        self.assertEqual(parse_ratio_parts("5:2:1"), [5, 2, 1])

    def test_weights_for_ratio_three_drivers(self):
        self.assertEqual(weights_for_ratio("1:2:3", 3), [1, 2, 3])

    def test_validate_ratio_requires_matching_part_count(self):
        self.assertIsNotNone(validate_ratio_for_slots("1:2", 3))

    def test_one_two_three_with_one_container_goes_to_b3(self):
        quotas = effective_integer_quotas([1, 2, 3], 1)
        self.assertEqual(quotas, [0, 0, 1])

    def test_three_driver_effective_label_shows_all_slots(self):
        self.assertEqual(effective_ratio_label([2, 1, 1], 3), "1:1:1")

    def test_simulated_assignment_three_drivers_one_two_three(self):
        rows = [
            SimpleNamespace(driver_id=10, vehicle_rz_id=1, sort_order=0, assignment_weight=1),
            SimpleNamespace(driver_id=20, vehicle_rz_id=2, sort_order=1, assignment_weight=2),
            SimpleNamespace(driver_id=30, vehicle_rz_id=3, sort_order=2, assignment_weight=3),
        ]
        counts: dict[tuple[int | None, int | None], int] = {}
        driver_id, _ = pick_weighted_assignment(rows, counts)
        self.assertEqual(driver_id, 30)
