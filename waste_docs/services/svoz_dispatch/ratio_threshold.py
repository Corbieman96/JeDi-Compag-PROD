"""Práh počtu požadavků pro aktivaci poměru řidičů B1–B4 (běžný svoz).

Výjimky matice V1–V4 tento modul neovlivňuje — platí jen pro RowKind.STANDARD.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from waste_docs.services.svoz_dispatch.ratio_quotas import weights_for_ratio

if TYPE_CHECKING:
    from waste_docs.models import SvozYardDriverPlan

DEFAULT_RATIO_MIN_CONTAINERS = 5
RATIO_MIN_FIELD_MAX = 99


def clamp_ratio_min(value) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_RATIO_MIN_CONTAINERS
    return max(1, min(RATIO_MIN_FIELD_MAX, parsed))


def ratio_min_containers_for_yard(yard_settings) -> int:
    """Minimální počet otevřených požadavků z nastavení sběrného dvora."""
    if yard_settings is None:
        return DEFAULT_RATIO_MIN_CONTAINERS
    raw = getattr(yard_settings, "yard_svoz_ratio_min_containers", None)
    if raw is None:
        return DEFAULT_RATIO_MIN_CONTAINERS
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_RATIO_MIN_CONTAINERS
    return clamp_ratio_min(value)


def ratio_min_for_yard_in_plan(
    *,
    yard_id: int,
    yard_settings,
    post_data=None,
) -> int:
    """Práh pro aktuální obrazovku plánu — při POST preferuje hodnotu z formuláře."""
    if post_data is not None:
        raw = (post_data.get(f"ratio_min_{yard_id}") or "").strip()
        if raw.isdigit():
            return clamp_ratio_min(int(raw))
    return ratio_min_containers_for_yard(yard_settings)


def validate_yard_ratio_mins_from_plan_post(post_data, yards) -> str | None:
    """Vrátí chybu, pokud je limit u některého dvora neplatný."""
    for y in yards:
        raw = (post_data.get(f"ratio_min_{y.pk}") or "").strip()
        if not raw:
            continue
        if not raw.isdigit():
            yard_name = y.company_name or f"dvůr #{y.pk}"
            return f"{yard_name}: limit požadavků pro poměr musí být celé číslo od 1 do {RATIO_MIN_FIELD_MAX}."
        if int(raw) < 1 or int(raw) > RATIO_MIN_FIELD_MAX:
            yard_name = y.company_name or f"dvůr #{y.pk}"
            return f"{yard_name}: limit požadavků pro poměr musí být od 1 do {RATIO_MIN_FIELD_MAX}."
    return None


def save_yard_ratio_mins_from_plan_post(post_data, yards) -> None:
    """Uloží limity poměru z plánu svozů do nastavení jednotlivých dvorů."""
    for y in yards:
        raw = (post_data.get(f"ratio_min_{y.pk}") or "").strip()
        if not raw or not raw.isdigit():
            continue
        value = clamp_ratio_min(int(raw))
        ys = getattr(y, "yard_settings", None)
        if ys is None:
            continue
        if ys.yard_svoz_ratio_min_containers == value:
            continue
        ys.yard_svoz_ratio_min_containers = value
        ys.save(update_fields=["yard_svoz_ratio_min_containers"])


def ratio_applies(
    *,
    filled_driver_count: int,
    open_task_count: int,
    ratio_min: int,
) -> bool:
    """True, pokud se má použít poměr mezi sloty B1–B4."""
    threshold = max(1, int(ratio_min or DEFAULT_RATIO_MIN_CONTAINERS))
    return filled_driver_count >= 2 and open_task_count >= threshold


def weights_for_plan_slots(
    *,
    ratio: str,
    slot_count: int,
    ratio_active: bool,
) -> list[int]:
    """
    Váhy slotů pro uložení plánu (zvolený poměr z formuláře).
    ratio_active ovlivňuje jen runtime přiřazení úkolů (plan_rows_for_weighted_assignment),
    ne uložený poměr v plánu.
    """
    del ratio_active
    if slot_count <= 0:
        return []
    if slot_count == 1:
        return [1]
    return weights_for_ratio(ratio, slot_count)


def ratio_inactive_hint(*, open_task_count: int, ratio_min: int, filled_driver_count: int) -> str:
    """Krátká nápověda pod řádkem druhu vozidla, když je poměr vypnutý."""
    if filled_driver_count < 2:
        return ""
    threshold = max(1, int(ratio_min or DEFAULT_RATIO_MIN_CONTAINERS))
    if open_task_count >= threshold:
        return ""
    return (
        f"Méně než {threshold} požadavků ({open_task_count}) — poměr neaktivní, "
        "vše přiřadí B1."
    )


def plan_rows_for_weighted_assignment(
    plan_rows: list[SvozYardDriverPlan],
    *,
    open_task_count: int,
    ratio_min: int,
) -> list[SvozYardDriverPlan]:
    """
    Řádky plánu pro vážené přiřazení běžného svozu.
    Pod prahem vrátí jen první slot (B1); jinak sloty s váhou > 0.
    """
    filled = [r for r in plan_rows if r.driver_id]
    if not filled:
        return []
    if not ratio_applies(
        filled_driver_count=len(filled),
        open_task_count=open_task_count,
        ratio_min=ratio_min,
    ):
        first = min(filled, key=lambda r: (r.sort_order, r.driver_id or 0))
        return [first]
    active = [r for r in filled if int(getattr(r, "assignment_weight", 1) or 0) > 0]
    return active if active else [min(filled, key=lambda r: (r.sort_order, r.driver_id or 0))]


def resolve_standard_assignment_plan_rows(
    plan_rows: list[SvozYardDriverPlan],
    *,
    plan_date,
    subject_profile_id: int,
    vehicle_kind_id: int | None,
    yard_settings=None,
) -> list[SvozYardDriverPlan]:
    """Plán pro pick_weighted_assignment — respektuje práh dvora (jen běžný svoz)."""
    from waste_docs.services.svoz_dispatch.standard_tasks_preview import (
        open_standard_tasks_preview_for_yard_kind,
    )

    if not vehicle_kind_id:
        filled = [r for r in plan_rows if r.driver_id]
        if not filled:
            return []
        first = min(filled, key=lambda r: (r.sort_order, r.driver_id or 0))
        return [first]
    open_count, _ = open_standard_tasks_preview_for_yard_kind(
        plan_date,
        subject_profile_id=subject_profile_id,
        vehicle_kind_id=int(vehicle_kind_id),
    )
    ratio_min = ratio_min_containers_for_yard(yard_settings)
    return plan_rows_for_weighted_assignment(
        plan_rows,
        open_task_count=open_count,
        ratio_min=ratio_min,
    )
