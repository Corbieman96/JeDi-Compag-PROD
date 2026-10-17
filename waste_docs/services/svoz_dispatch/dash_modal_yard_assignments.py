"""Shrnutí denního plánu řidičů u dvorů pro modal Jízdy na dashboardu."""

from __future__ import annotations

from collections import defaultdict

from waste_docs.models import SvozYardDriverPlan
from waste_docs.services.svoz_dispatch.collection_yard_day_bundle import (
    get_collection_yard_day_bundle,
)
from waste_docs.services.svoz_dispatch.exception_slot import exception_slot_labels_for_plan


def plan_row_label_for_assignment(
    row: SvozYardDriverPlan,
    *,
    exception_labels: dict[tuple[int, int, int], str],
) -> str:
    """Text řádku plánu — běžný svoz B1–B4 nebo název výjimky z matice."""
    if row.row_kind == SvozYardDriverPlan.RowKind.STANDARD:
        return f"Běžný svoz B{int(row.sort_order) + 1}"
    slot = int(row.sort_order) + 1
    vk_id = row.vehicle_kind_id
    if vk_id:
        label = exception_labels.get((row.subject_profile_id, int(vk_id), slot), "").strip()
        if label:
            return label
    return f"Výjimka V{slot}"


def yard_driver_assignment_cards_for_date(plan_date):
    """
    Jedna karta na každý sběrný dvůr (pořadí jako v číselníku).
    assignments — řádky z plánu (sloty); prázdné pole = u dvoru není přiřazený řidič.
    """
    bundle = get_collection_yard_day_bundle(plan_date)
    yards = list(bundle.yards)
    if not yards:
        return []
    yard_ids = [y.pk for y in yards]
    exception_labels = exception_slot_labels_for_plan(yard_ids)
    by_yard: dict[int, list[dict]] = defaultdict(list)
    for r in bundle.plan_rows:
        driver = r.driver
        driver_label = " ".join(
            p for p in (driver.last_name, driver.first_name) if (p or "").strip()
        ).strip() or str(driver)
        rz_label = ""
        if r.vehicle_rz_id and r.vehicle_rz:
            rz_label = (r.vehicle_rz.value or "").strip()
        vk_short = ""
        if r.vehicle_kind_id and r.vehicle_kind:
            vk_short = r.vehicle_kind.display_label()
        by_yard[r.subject_profile_id].append(
            {
                "driver_label": driver_label,
                "rz_label": rz_label or None,
                "vehicle_kind_short": vk_short or None,
                "plan_label": plan_row_label_for_assignment(r, exception_labels=exception_labels),
            }
        )
    cards = []
    for y in yards:
        slots = by_yard.get(y.pk, [])
        cards.append(
            {
                "yard_id": y.pk,
                "yard_name": (y.company_name or "").strip() or f"Sběrný dvůr #{y.pk}",
                "assignments": slots,
                "has_drivers": bool(slots),
            }
        )
    return cards
