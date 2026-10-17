"""Vážený výběr řidiče ze slotů plánu svozů (poměr 1:3 apod.)."""

from __future__ import annotations

from waste_docs.models import SvozYardDriverPlan


def pick_weighted_plan_row(
    plan_rows: list[SvozYardDriverPlan],
    counts: dict[tuple[int | None, int | None], int],
) -> SvozYardDriverPlan | None:
    """
    Vybere slot s nejnižším poměrem počet_úkolů / váha.
    counts: (driver_id, vehicle_rz_id) -> počet úkolů za den u dvora.
    """
    best: SvozYardDriverPlan | None = None
    best_key: tuple | None = None
    for row in plan_rows:
        if not row.driver_id:
            continue
        weight = int(getattr(row, "assignment_weight", 1) or 0)
        if weight <= 0:
            continue
        key = (row.driver_id, row.vehicle_rz_id)
        task_count = counts.get(key, 0)
        weight = max(1, weight)
        sort_key = (
            task_count / weight,
            -weight,
            row.sort_order,
            row.driver_id,
            row.vehicle_rz_id or 0,
        )
        if best_key is None or sort_key < best_key:
            best_key = sort_key
            best = row
    if best is None:
        return None
    return best


def pick_weighted_assignment(
    plan_rows: list[SvozYardDriverPlan],
    counts: dict[tuple[int | None, int | None], int],
) -> tuple[int | None, int | None]:
    row = pick_weighted_plan_row(plan_rows, counts)
    if row is None:
        return None, None
    return row.driver_id, row.vehicle_rz_id
