from __future__ import annotations

from datetime import date

from django.urls import reverse


def parse_selected_ride_pk(raw: str, selected_ride_group: dict | None) -> int | None:
    if not raw or not selected_ride_group:
        return None
    try:
        pk = int(raw.strip())
    except (TypeError, ValueError):
        return None
    item_pks = {r.pk for r in selected_ride_group.get("items") or []}
    return pk if pk in item_pks else None


def filter_pks_for_email_group(group: dict, selected_ride_pk: int | None) -> list[int]:
    """PK jízd pro e-mail — stejná logika jako tisk z detailu jízdy."""
    items = group.get("items") or []
    if not items:
        return []
    item_pks = {r.pk for r in items}
    if selected_ride_pk is not None and selected_ride_pk in item_pks:
        return [selected_ride_pk]
    return [r.pk for r in items]


def print_pks_for_group(group: dict, selected_ride_pk: int | None) -> str:
    items = group.get("items") or []
    if not items:
        return ""
    item_pks = {r.pk for r in items}
    if selected_ride_pk is not None and selected_ride_pk in item_pks:
        return str(selected_ride_pk)
    if len(items) == 1:
        return str(items[0].pk)
    return ""


def ride_print_bundle_url(drive_date: date, vehicle_rz_id: int, pks: str = "") -> str:
    base = reverse("waste_docs:ride_print_bundle")
    query = f"date={drive_date.isoformat()}&vehicle_rz_id={vehicle_rz_id}"
    if pks:
        query += f"&pks={pks}"
    return f"{base}?{query}"


def dashboard_header_print_url(
    selected_date: date,
    selected_ride_group: dict | None,
    selected_ride_pk: int | None,
    *,
    ride_group_explicit: bool,
) -> str:
    if (
        ride_group_explicit
        and selected_ride_group
        and selected_ride_group.get("vehicle_rz_id")
        and not selected_ride_group.get("is_plan_only")
    ):
        rz_id = int(selected_ride_group["vehicle_rz_id"])
        drive_date = selected_ride_group["drive_date"]
        if selected_ride_pk:
            pks = str(selected_ride_pk)
        else:
            items = selected_ride_group.get("items") or []
            pks = ",".join(str(r.pk) for r in items)
        if pks:
            return ride_print_bundle_url(drive_date, rz_id, pks)
    return f"{reverse('waste_docs:dashboard_bulk_print')}?date={selected_date.isoformat()}"


def annotate_ride_groups_print_pks(ride_groups: list[dict], selected_ride_pk: int | None) -> None:
    for group in ride_groups:
        if group.get("is_plan_only"):
            group["print_pks"] = ""
        else:
            group["print_pks"] = print_pks_for_group(group, selected_ride_pk)
