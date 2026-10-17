"""Klíče a lookup skupin jízd na dashboardu (den + RZ + řidič)."""

from __future__ import annotations

from datetime import date


def ride_group_key(drive_date: date, vehicle_rz_id: int | None, driver_id: int | None) -> str:
    """Stabilní klíč skupiny jízd pro URL a seskupení."""
    iso = drive_date.isoformat()
    rz = int(vehicle_rz_id or 0)
    drv = int(driver_id or 0)
    return f"{iso}::{rz}::{drv}"


def plan_only_ride_group_key(drive_date: date, vehicle_rz_id: int, driver_id: int) -> str:
    return f"{ride_group_key(drive_date, vehicle_rz_id, driver_id)}::plan"


def parse_ride_group_key(key: str) -> tuple[date | None, int | None, int | None, bool]:
    """
    Vrátí (drive_date, vehicle_rz_id, driver_id, is_plan_only).
    Neplatný klíč → (None, None, None, False).
    """
    raw = (key or "").strip()
    if not raw:
        return None, None, None, False
    is_plan = raw.endswith("::plan")
    if is_plan:
        raw = raw[: -len("::plan")]
    parts = raw.split("::")
    if len(parts) < 2:
        return None, None, None, is_plan
    try:
        drive_date = date.fromisoformat(parts[0])
    except ValueError:
        return None, None, None, is_plan
    try:
        rz_id = int(parts[1])
    except (TypeError, ValueError):
        return None, None, None, is_plan
    driver_id: int | None = None
    if len(parts) >= 3:
        try:
            driver_id = int(parts[2])
        except (TypeError, ValueError):
            driver_id = None
    return drive_date, rz_id, driver_id, is_plan


def resolve_ride_group(ride_groups: list[dict], key: str) -> dict | None:
    """Najde skupinu podle klíče; starý formát `{date}::{rz_id}` mapuje na první shodu RZ."""
    if not key:
        return None
    exact = next((g for g in ride_groups if g.get("key") == key), None)
    if exact is not None:
        return exact
    drive_date, rz_id, driver_id, is_plan = parse_ride_group_key(key)
    if drive_date is None or rz_id is None:
        return None
    if driver_id is not None:
        for group in ride_groups:
            if (
                group.get("drive_date") == drive_date
                and group.get("vehicle_rz_id") == rz_id
                and group.get("driver_id") == driver_id
                and bool(group.get("is_plan_only")) == is_plan
            ):
                return group
        return None
    for group in ride_groups:
        if (
            group.get("drive_date") == drive_date
            and group.get("vehicle_rz_id") == rz_id
            and not group.get("is_plan_only")
        ):
            return group
    return None
