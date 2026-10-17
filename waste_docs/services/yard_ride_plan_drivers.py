"""Řidiči pro založení průvodky ze sběrného dvora (nova-jizda) — plán dvora + dnešní jízdy."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from catalogs.models import DriverProfile, NameSubjectProfile
from catalogs.services.driver_absence import driver_ids_fully_absent_on_date
from waste_docs.models import Pruvodka, SvozYardDriverPlan


def driver_display_label(driver: DriverProfile) -> str:
    full_name = " ".join(part for part in [driver.last_name, driver.first_name] if part).strip()
    personal_number = (driver.personal_number or "").strip()
    if full_name and personal_number and personal_number not in full_name:
        return f"{full_name} ({personal_number})"
    return full_name or personal_number or str(driver.pk)


def _driver_entry(driver: DriverProfile) -> dict:
    return {"id": int(driver.pk), "label": driver_display_label(driver)}


def drivers_by_rz_for_yard_plan(
    subject: NameSubjectProfile,
    plan_date: date,
) -> dict[int, list[dict]]:
    """
    Mapa vehicle_rz_id → seznam řidičů z plánu na daný den u dvora.
    Každý řidič jen jednou per RZ (deduplikace).
    """
    rows = (
        SvozYardDriverPlan.objects.filter(
            plan_date=plan_date,
            subject_profile=subject,
            vehicle_rz_id__isnull=False,
        )
        .select_related("driver")
        .order_by("sort_order", "driver_id")
    )
    out: dict[int, list[dict]] = defaultdict(list)
    seen: dict[int, set[int]] = defaultdict(set)
    for row in rows:
        rz_id = int(row.vehicle_rz_id)
        driver_id = int(row.driver_id)
        if driver_id in seen[rz_id]:
            continue
        seen[rz_id].add(driver_id)
        out[rz_id].append(_driver_entry(row.driver))
    return dict(out)


def _drivers_from_pruvodky(plan_date: date) -> dict[int, list[dict]]:
    """Řidiči z nearchivovaných průvodk za den, seskupení podle RZ."""
    absent_ids = driver_ids_fully_absent_on_date(plan_date)
    rows = (
        Pruvodka.objects.filter(
            drive_date=plan_date,
            is_archived=False,
            vehicle_rz_id__isnull=False,
            driver_id__isnull=False,
        )
        .exclude(driver_id__in=absent_ids)
        .select_related("driver")
        .order_by("driver__last_name", "driver__first_name", "driver_id")
    )
    out: dict[int, list[dict]] = defaultdict(list)
    seen: dict[int, set[int]] = defaultdict(set)
    for row in rows:
        rz_id = int(row.vehicle_rz_id)
        driver_id = int(row.driver_id)
        if driver_id in seen[rz_id]:
            continue
        seen[rz_id].add(driver_id)
        out[rz_id].append(_driver_entry(row.driver))
    return dict(out)


def drivers_by_rz_for_yard_day(
    subject: NameSubjectProfile,
    plan_date: date,
) -> dict[int, list[dict]]:
    """
    Mapa vehicle_rz_id → řidiči pro nova-jizda: plán aktuálního dvora + dnešní jízdy na RZ.
    """
    absent_ids = driver_ids_fully_absent_on_date(plan_date)
    plan_map = drivers_by_rz_for_yard_plan(subject, plan_date)
    rides_map = _drivers_from_pruvodky(plan_date)

    out: dict[int, list[dict]] = defaultdict(list)
    seen: dict[int, set[int]] = defaultdict(set)

    for source in (plan_map, rides_map):
        for rz_id, drivers in source.items():
            for entry in drivers:
                driver_id = int(entry["id"])
                if driver_id in absent_ids or driver_id in seen[rz_id]:
                    continue
                seen[rz_id].add(driver_id)
                out[rz_id].append(entry)

    return dict(out)


def driver_allowed_for_yard_rz(
    subject: NameSubjectProfile,
    plan_date: date,
    vehicle_rz_id: int,
    driver_id: int,
) -> bool:
    allowed = drivers_by_rz_for_yard_day(subject, plan_date).get(int(vehicle_rz_id), [])
    return any(int(d["id"]) == int(driver_id) for d in allowed)


def drivers_by_rz_json_map(
    subject: NameSubjectProfile,
    plan_date: date,
) -> dict[str, list[dict]]:
    """Mapa pro json_script — klíče RZ jako řetězce."""
    raw = drivers_by_rz_for_yard_day(subject, plan_date)
    return {str(rz_id): drivers for rz_id, drivers in raw.items()}
