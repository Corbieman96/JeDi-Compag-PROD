from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from catalogs.models import NameSubjectProfile, VehicleKindCatalog, VehicleRzProfile
from core.services.ride_email_dispatch_status import attach_email_dispatch_to_ride_groups
from core.services.ride_grouping import resolve_ride_group, ride_group_key
from users.services.access import can_see_all_waste_docs
from waste_docs.models import Pruvodka
from waste_docs.ride_group_status import ride_group_count_meta, ride_group_status_label
from waste_docs.services.blank_pruvodka import is_unused_blank_pruvodka
from waste_docs.services.svoz_dispatch.dashboard_plan_bridge import planned_svoz_vehicle_groups
from waste_docs.services.ride_print_order import sort_rides_list
from core.services.ride_group_reorder import ride_group_has_mixed_snd_groups


def _vehicle_kind_tags_for_group(
    group: dict,
    profile_by_rz: dict,
    kinds_ordered: list[VehicleKindCatalog],
) -> list[dict]:
    """Zkratky druhů vozidla pro skupinu jízd (pořadí dle číselníku)."""
    rz_id = group.get("vehicle_rz_id")
    if not rz_id:
        return []
    prof = profile_by_rz.get(rz_id)
    if not prof:
        return []
    kind_ids = {k.pk for k in prof.vehicle_kinds.all()}
    return [
        {"shortcut": k.shortcut, "title": k.display_label()}
        for k in kinds_ordered
        if k.pk in kind_ids
    ]


def org_occupied_rz_driver_pairs(selected_date) -> frozenset[tuple[int, int]]:
    """Páry (RZ, řidič), pro které už za den existuje nearchivovaná průvodka."""
    pairs: set[tuple[int, int]] = set()
    for rz_id, driver_id in (
        Pruvodka.objects.filter(drive_date=selected_date, is_archived=False)
        .exclude(vehicle_rz_id__isnull=True)
        .values_list("vehicle_rz_id", "driver_id")
    ):
        pairs.add((int(rz_id), int(driver_id or 0)))
    return frozenset(pairs)


def org_occupied_vehicle_rz_ids(selected_date) -> frozenset[int]:
    """RZ s alespoň jednou průvodkou za den — zpětná kompatibilita starších volání."""
    return frozenset(rz for rz, _ in org_occupied_rz_driver_pairs(selected_date))


def _driver_last_name_for_group(items: list[Pruvodka]) -> str:
    for ride in items:
        if ride.driver_id and ride.driver and (ride.driver.last_name or "").strip():
            return (ride.driver.last_name or "").strip()
    for ride in items:
        snap = (ride.driver_snapshot or "").strip()
        if snap:
            return snap.split()[-1]
    return "—"


def build_dashboard_rides_section(
    user: AbstractBaseUser,
    selected_date,
    selected_ride_group_key: str,
) -> tuple[dict, object]:
    rides_qs = Pruvodka.objects.all()
    if not can_see_all_waste_docs(user):
        rides_qs = rides_qs.filter(created_by=user)

    rides_day_qs = rides_qs.filter(drive_date=selected_date, is_archived=False)
    rides = list(
        rides_day_qs.select_related("vehicle_rz", "driver", "activity", "name").order_by(
            "-drive_date", "-created_at", "-pk"
        )
    )
    dash_modal_yard_name_ids = frozenset()
    if rides:
        name_ids = {r.name_id for r in rides if getattr(r, "name_id", None)}
        if name_ids:
            dash_modal_yard_name_ids = frozenset(
                NameSubjectProfile.objects.filter(
                    name_id__in=name_ids,
                    yard_settings__is_collection_yard=True,
                ).values_list("name_id", flat=True)
            )
    dashboard_has_pending_generation = any(
        (not ride.generated_file) and not (ride.activity and ride.activity.evidence_without_excel)
        for ride in rides
    )
    ride_groups = []
    ride_groups_map = {}
    for ride in rides:
        group_key = ride_group_key(ride.drive_date, ride.vehicle_rz_id, ride.driver_id)
        group = ride_groups_map.get(group_key)
        if not group:
            group = {
                "key": group_key,
                "drive_date": ride.drive_date,
                "vehicle_rz_id": ride.vehicle_rz_id,
                "vehicle_rz": ride.vehicle_rz_snapshot or "—",
                "driver_id": ride.driver_id or 0,
                "items": [],
            }
            ride_groups_map[group_key] = group
            ride_groups.append(group)
        group["items"].append(ride)

    ride_groups.extend(
        planned_svoz_vehicle_groups(selected_date, org_occupied_rz_driver_pairs(selected_date)),
    )

    for group in ride_groups:
        if group.get("is_plan_only"):
            continue
        items = group["items"]
        blank_items = [r for r in items if getattr(r, "is_blank_pruvodka", False)]
        if blank_items:
            group["is_blank_group"] = True
            group["blank_print_pks"] = ",".join(str(r.pk) for r in blank_items)
        if items and all(getattr(r, "is_blank_pruvodka", False) for r in items):
            status = "Bianko"
        else:
            status = ride_group_status_label(items)
        group["status"] = status
        group["count_meta"] = ride_group_count_meta(status, len(items))
        group["driver_last_name"] = _driver_last_name_for_group(items)
        group["items"] = sort_rides_list(items)
        group["has_mixed_snd_groups"] = ride_group_has_mixed_snd_groups(group["items"])
        group["has_manual_route_order"] = any((r.ride_route_order or 0) > 0 for r in group["items"])

    rz_ids = {g["vehicle_rz_id"] for g in ride_groups if g.get("vehicle_rz_id")}
    profile_by_rz = {}
    if rz_ids:
        profiles = VehicleRzProfile.objects.filter(rz_id__in=rz_ids).prefetch_related("vehicle_kinds")
        profile_by_rz = {p.rz_id: p for p in profiles}

    # Jednou v paměti (prefetch) — bez N+1 .exists() / opakovaných dotazů.
    kind_ids_by_rz = {
        rz_id: {k.pk for k in prof.vehicle_kinds.all()}
        for rz_id, prof in profile_by_rz.items()
    }

    kinds_ordered = list(VehicleKindCatalog.objects.order_by("sort_order", "name", "pk"))

    for group in ride_groups:
        tags = _vehicle_kind_tags_for_group(group, profile_by_rz, kinds_ordered)
        group["vehicle_kind_tags"] = tags
        group["vehicle_kind_shortcuts_label"] = " · ".join(t["shortcut"] for t in tags)
        prof = profile_by_rz.get(group.get("vehicle_rz_id"))
        group["vehicle_rz_note"] = (
            (prof.vehicle_type or "").strip() if prof is not None else ""
        )

    def _ride_group_sort_key(g):
        return ((g["vehicle_rz"] or "").lower(), (g.get("driver_last_name") or "").lower())

    ride_group_columns = []
    for kind in kinds_ordered:
        col_groups = []
        for group in ride_groups:
            rz_id = group.get("vehicle_rz_id")
            if not rz_id:
                continue
            kind_ids = kind_ids_by_rz.get(rz_id)
            if kind_ids is None:
                continue
            if kind.pk in kind_ids:
                col_groups.append(group)
        col_groups.sort(key=_ride_group_sort_key)
        ride_group_columns.append({"kind": kind, "groups": col_groups})

    ride_groups_uncategorized = []
    for group in ride_groups:
        rz_id = group.get("vehicle_rz_id")
        if not rz_id:
            ride_groups_uncategorized.append(group)
            continue
        kind_ids = kind_ids_by_rz.get(rz_id)
        if kind_ids is None or not kind_ids:
            ride_groups_uncategorized.append(group)
            continue
    ride_groups_uncategorized.sort(key=_ride_group_sort_key)

    selected_ride_group = resolve_ride_group(ride_groups, selected_ride_group_key) if selected_ride_group_key else None

    attach_email_dispatch_to_ride_groups(ride_groups, selected_date)

    blank_pruvodka_unused_count = sum(1 for r in rides if is_unused_blank_pruvodka(r))

    ctx = {
        "docs_count": len(rides),
        "generated_count": sum(1 for r in rides if r.status == Pruvodka.Status.GENERATED),
        "rides": rides,
        "ride_groups": ride_groups,
        "blank_pruvodka_unused_count": blank_pruvodka_unused_count,
        "dashboard_has_pending_generation": dashboard_has_pending_generation,
        "ride_group_columns": ride_group_columns,
        "dash_modal_yard_name_ids": dash_modal_yard_name_ids,
        "ride_groups_uncategorized": ride_groups_uncategorized,
        "selected_ride_group": selected_ride_group,
    }
    return ctx, rides_day_qs
