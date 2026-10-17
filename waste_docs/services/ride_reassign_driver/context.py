"""Context pro dashboard modal — výměna řidiče."""

from __future__ import annotations

import json

from django.contrib.auth.models import AbstractBaseUser
from django.urls import reverse
from django.utils.safestring import mark_safe

from catalogs.models import VehicleRzCatalog
from users.services.waste_doc_permissions import can_edit_existing_pruvodka
from waste_docs.services.ride_reassign_driver.eligibility import (
    driver_rz_options_map,
    eligible_drivers_for_kind,
    format_rz_option_label,
    resolve_vehicle_kind_id_for_rides,
)


def build_ride_reassign_driver_context(
    selected_ride_group: dict | None,
    user: AbstractBaseUser,
) -> dict:
    empty = {
        "ride_reassign_driver_enabled": False,
        "ride_reassign_driver": None,
        "ride_reassign_driver_json": mark_safe("{}"),
    }
    if not selected_ride_group or selected_ride_group.get("is_plan_only"):
        return empty
    items = list(selected_ride_group.get("items") or [])
    if not items:
        return empty
    if not any(can_edit_existing_pruvodka(user, r) for r in items):
        return empty

    kind_id = resolve_vehicle_kind_id_for_rides(items)
    if not kind_id:
        return empty

    drivers = eligible_drivers_for_kind(kind_id)
    rz_by_driver = driver_rz_options_map(drivers=drivers)
    current_rz_id = int(selected_ride_group.get("vehicle_rz_id") or 0) or None
    current_driver_id = int(selected_ride_group.get("driver_id") or 0) or None
    drive_date = selected_ride_group.get("drive_date")

    rides_payload = []
    for ride in items:
        label = f"#{ride.pk}"
        if getattr(ride, "snd_cislo_listu", None):
            label = f"{label} ({ride.snd_cislo_listu})"
        rides_payload.append(
            {
                "pk": int(ride.pk),
                "label": label,
                "name": (ride.name_snapshot or "—").strip() or "—",
                "waste": (ride.waste_type_snapshot or "—").strip() or "—",
            }
        )

    drivers_payload = []
    for d in drivers:
        rz_rows = rz_by_driver.get(int(d.pk), [])
        drivers_payload.append(
            {
                "id": int(d.pk),
                "label": str(d),
                "rz_ids": [row["id"] for row in rz_rows],
            }
        )

    # Union RZ options for initial select (filtered by JS after driver pick).
    rz_seen: dict[int, str] = {}
    for rows in rz_by_driver.values():
        for row in rows:
            rz_seen[int(row["id"])] = row["label"]
    if current_rz_id and current_rz_id not in rz_seen:
        rz_obj = (
            VehicleRzCatalog.objects.filter(pk=current_rz_id)
            .select_related("profile")
            .prefetch_related("profile__vehicle_kinds")
            .first()
        )
        if rz_obj:
            rz_seen[current_rz_id] = format_rz_option_label(rz_obj, eligible_drivers=drivers)
        else:
            snap = (selected_ride_group.get("vehicle_rz") or "").strip()
            if snap and snap != "—":
                rz_seen[current_rz_id] = snap

    payload = {
        "post_url": reverse("waste_docs:ride_reassign_driver"),
        "drive_date": drive_date.isoformat() if drive_date else "",
        "from_vehicle_rz_id": current_rz_id or 0,
        "from_driver_id": current_driver_id or 0,
        "vehicle_kind_id": int(kind_id),
        "current_rz_id": current_rz_id or 0,
        "current_driver_id": current_driver_id or 0,
        "rides": rides_payload,
        "drivers": drivers_payload,
        "rz_by_driver": {str(k): v for k, v in rz_by_driver.items()},
        "rz_options": [{"id": i, "label": lab} for i, lab in sorted(rz_seen.items(), key=lambda x: x[1])],
    }

    return {
        "ride_reassign_driver_enabled": True,
        "ride_reassign_driver": payload,
        "ride_reassign_driver_json": mark_safe(json.dumps(payload, ensure_ascii=False)),
    }
