"""Skupiny vozidel z plánu svozů pro dashboard — jeden řádek na řidiče + RZ."""

from __future__ import annotations

from datetime import date

from core.services.ride_grouping import plan_only_ride_group_key
from waste_docs.services.svoz_dispatch.collection_yard_day_bundle import (
    get_collection_yard_day_bundle,
)


def _collection_yard_ids(plan_date: date) -> frozenset[int]:
    """Stejně jako plán svozů jen pro subjekty se sběrným dvorem."""
    return get_collection_yard_day_bundle(plan_date).yard_ids


def driver_ids_with_planned_svoz_slots(plan_date: date) -> frozenset[int]:
    """ID řidičů, které má plán pro den s vybraným RZ (slot opravdu naplánován)."""
    bundle = get_collection_yard_day_bundle(plan_date)
    if not bundle.yard_ids:
        return frozenset()
    return frozenset(
        int(row.driver_id)
        for row in bundle.plan_rows
        if row.vehicle_rz_id is not None and row.driver_id is not None
    )


def planned_svoz_vehicle_groups(
    plan_date: date,
    occupied_rz_driver_pairs: frozenset[tuple[int, int]],
) -> list[dict]:
    """
    Skupiny z plánu — jeden řádek na každý slot (řidič + RZ), pokud pro daný pár
    ještě neexistuje nearchivovaná průvodka se stejným řidičem a RZ.
    """
    bundle = get_collection_yard_day_bundle(plan_date)
    if not bundle.yard_ids:
        return []

    seen: set[tuple[int, int]] = set()
    out: list[dict] = []
    for row in bundle.plan_rows:
        rz_id = row.vehicle_rz_id
        driver_id = row.driver_id
        if rz_id is None or driver_id is None:
            continue
        pair = (int(rz_id), int(driver_id))
        if pair in seen or pair in occupied_rz_driver_pairs:
            continue
        seen.add(pair)
        driver_last_name = (row.driver.last_name or "").strip() if row.driver else ""
        out.append(
            {
                "key": plan_only_ride_group_key(plan_date, rz_id, driver_id),
                "drive_date": plan_date,
                "vehicle_rz_id": rz_id,
                "vehicle_rz": (row.vehicle_rz.value or "").strip() or "—",
                "driver_id": driver_id,
                "items": [],
                "status": "Plán svozů",
                "count_meta": "0 průvodek · čeká na úkoly",
                "driver_last_name": driver_last_name or "—",
                "is_plan_only": True,
            }
        )
    out.sort(key=lambda g: ((g["vehicle_rz"] or "").lower(), (g["driver_last_name"] or "").lower()))
    return out
