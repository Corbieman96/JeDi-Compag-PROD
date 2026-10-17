from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from waste_docs.services.svoz_dispatch.weighted_assignment import pick_weighted_assignment


class SvozWeightedAssignmentTests(TestCase):
    def _row(self, driver_id: int, rz_id: int, sort_order: int, weight: int):
        return SimpleNamespace(
            driver_id=driver_id,
            vehicle_rz_id=rz_id,
            sort_order=sort_order,
            assignment_weight=weight,
        )

    def test_single_driver_always_selected(self):
        rows = [self._row(10, 1, 0, 1)]
        driver_id, rz_id = pick_weighted_assignment(rows, {})
        self.assertEqual((driver_id, rz_id), (10, 1))

    def test_empty_counts_picks_higher_weight_slot(self):
        rows = [
            self._row(10, 1, 0, 1),
            self._row(20, 2, 1, 3),
        ]
        driver_id, _ = pick_weighted_assignment(rows, {})
        self.assertEqual(driver_id, 20)

    def test_empty_counts_two_one_picks_b1(self):
        rows = [
            self._row(10, 1, 0, 2),
            self._row(20, 2, 1, 1),
        ]
        driver_id, _ = pick_weighted_assignment(rows, {})
        self.assertEqual(driver_id, 10)

    def test_zero_weight_row_ignored(self):
        rows = [
            self._row(10, 1, 0, 1),
            self._row(20, 2, 1, 0),
        ]
        driver_id, _ = pick_weighted_assignment(rows, {})
        self.assertEqual(driver_id, 10)

    def test_ratio_1_3_after_b1_has_three_tasks_picks_b2(self):
        rows = [
            self._row(10, 1, 0, 1),
            self._row(20, 2, 1, 3),
        ]
        counts = {(10, 1): 3, (20, 2): 0}
        driver_id, _ = pick_weighted_assignment(rows, counts)
        self.assertEqual(driver_id, 20)
