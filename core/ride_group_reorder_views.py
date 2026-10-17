"""API pro ruční řazení zastávek jízdy na dashboardu."""

from __future__ import annotations

import json
from datetime import datetime

from urllib.parse import unquote

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from core.services.ride_group_ai_prompt import build_ride_group_ai_prompt
from core.services.ride_group_reorder import (
    queryset_for_dashboard_ride_group,
    reorder_ride_group_items,
    reset_ride_group_route_order,
    ride_group_has_mixed_snd_groups,
)
from core.services.ride_route_optimizer import format_route_order_output, optimize_route_order
from core.services.ride_route_reorder.container_labels import load_passport_map
from core.services.ride_grouping import parse_ride_group_key
from users.services.access import can_see_all_waste_docs
from waste_docs.services.ride_print_order import sort_rides_list


def _require_dispatcher(user):
    if not user.is_authenticated or not can_see_all_waste_docs(user):
        raise Http404


def _parse_group_from_request(request):
    drive_date_raw = (request.GET.get("date") or request.POST.get("date") or "").strip()
    if not drive_date_raw:
        return None, "Chybí datum jízdy."
    try:
        drive_date = datetime.strptime(drive_date_raw, "%Y-%m-%d").date()
    except ValueError:
        return None, "Neplatné datum."

    ride_group = (request.GET.get("ride_group") or request.POST.get("ride_group") or "").strip()
    if ride_group:
        ride_group = unquote(ride_group)
        parsed_date, rz_id, driver_id, is_plan = parse_ride_group_key(ride_group)
        if is_plan or parsed_date is None:
            return None, "Neplatná skupina jízdy."
        if parsed_date != drive_date:
            return None, "Datum neodpovídá skupině jízdy."
        return (drive_date, rz_id, driver_id), None

    rz_raw = (request.GET.get("vehicle_rz_id") or request.POST.get("vehicle_rz_id") or "").strip()
    drv_raw = (request.GET.get("driver_id") or request.POST.get("driver_id") or "").strip()
    if not rz_raw.isdigit():
        return None, "Chybí identifikace jízdy."
    vehicle_rz_id = int(rz_raw) or None
    driver_id = int(drv_raw) if drv_raw.isdigit() and int(drv_raw) > 0 else None
    return (drive_date, vehicle_rz_id, driver_id), None


def _load_group_items(drive_date, vehicle_rz_id, driver_id):
    qs = queryset_for_dashboard_ride_group(
        drive_date=drive_date,
        vehicle_rz_id=vehicle_rz_id,
        driver_id=driver_id,
    )
    items = list(
        qs.select_related(
            "activity",
            "name",
            "driver",
            "container_passport",
            "container_passport__vehicle_kind",
            "follow_up_parent",
        )
    )
    if not items:
        return None
    return sort_rides_list(items)


@login_required
@require_POST
def ride_group_reorder(request):
    _require_dispatcher(request.user)
    group, err = _parse_group_from_request(request)
    if err:
        return JsonResponse({"ok": False, "error": err}, status=400)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Neplatný JSON."}, status=400)

    if payload.get("reset"):
        drive_date, vehicle_rz_id, driver_id = group
        count = reset_ride_group_route_order(
            drive_date=drive_date,
            vehicle_rz_id=vehicle_rz_id,
            driver_id=driver_id,
        )
        return JsonResponse({"ok": True, "changed": count, "reset": True})

    order = payload.get("order")
    if not isinstance(order, list) or not order:
        return JsonResponse({"ok": False, "error": "Chybí pole order."}, status=400)
    try:
        ordered_pks = [int(x) for x in order]
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Neplatné ID průvodek."}, status=400)

    drive_date, vehicle_rz_id, driver_id = group
    changed, warnings = reorder_ride_group_items(
        drive_date=drive_date,
        vehicle_rz_id=vehicle_rz_id,
        driver_id=driver_id,
        ordered_pks=ordered_pks,
    )
    if changed == 0 and warnings and warnings[0] in (
        "Skupina jízdy neobsahuje žádné průvodky.",
        "Pořadí musí obsahovat všechny průvodky ve skupině.",
        "Neplatná sada průvodek pro tuto jízdu.",
    ):
        return JsonResponse({"ok": False, "error": warnings[0]}, status=400)
    return JsonResponse({"ok": True, "changed": changed, "warnings": warnings})


@login_required
@require_GET
def ride_group_ai_prompt(request):
    _require_dispatcher(request.user)
    group, err = _parse_group_from_request(request)
    if err:
        return JsonResponse({"ok": False, "error": err}, status=400)

    drive_date, vehicle_rz_id, driver_id = group
    items = _load_group_items(drive_date, vehicle_rz_id, driver_id)
    if not items:
        return JsonResponse({"ok": False, "error": "Skupina jízdy neobsahuje průvodky."}, status=404)

    vehicle_rz = (items[0].vehicle_rz_snapshot or "").strip() or "—"
    driver_label = (items[0].driver_snapshot or "").strip()
    if not driver_label and items[0].driver_id and items[0].driver:
        driver_label = (items[0].driver.last_name or "").strip()
    prompt = build_ride_group_ai_prompt(
        drive_date=drive_date,
        vehicle_rz=vehicle_rz,
        driver_label=driver_label or "—",
        items=items,
    )
    return JsonResponse(
        {
            "ok": True,
            "prompt": prompt,
            "mixed_snd_groups": ride_group_has_mixed_snd_groups(items),
        }
    )


@login_required
@require_GET
def ride_group_optimize(request):
    _require_dispatcher(request.user)
    group, err = _parse_group_from_request(request)
    if err:
        return JsonResponse({"ok": False, "error": err}, status=400)

    drive_date, vehicle_rz_id, driver_id = group
    items = _load_group_items(drive_date, vehicle_rz_id, driver_id)
    if not items:
        return JsonResponse({"ok": False, "error": "Skupina jízdy neobsahuje průvodky."}, status=404)

    container_numbers: set[str] = set()
    for ride in items:
        for num in [(ride.container_number or "").strip(), (ride.container_number_2 or "").strip()]:
            if num:
                container_numbers.add(num)
    passport_map = load_passport_map(container_numbers)
    order = optimize_route_order(items, passport_map=passport_map)
    return JsonResponse(
        {
            "ok": True,
            "order": order,
            "output": format_route_order_output(order),
            "mixed_snd_groups": ride_group_has_mixed_snd_groups(items),
        }
    )


@login_required
@require_POST
def ride_group_optimize_apply(request):
    _require_dispatcher(request.user)
    group, err = _parse_group_from_request(request)
    if err:
        return JsonResponse({"ok": False, "error": err}, status=400)

    drive_date, vehicle_rz_id, driver_id = group
    items = _load_group_items(drive_date, vehicle_rz_id, driver_id)
    if not items:
        return JsonResponse({"ok": False, "error": "Skupina jízdy neobsahuje průvodky."}, status=404)

    container_numbers: set[str] = set()
    for ride in items:
        for num in [(ride.container_number or "").strip(), (ride.container_number_2 or "").strip()]:
            if num:
                container_numbers.add(num)
    order = optimize_route_order(items, passport_map=load_passport_map(container_numbers))
    changed, warnings = reorder_ride_group_items(
        drive_date=drive_date,
        vehicle_rz_id=vehicle_rz_id,
        driver_id=driver_id,
        ordered_pks=order,
    )
    if changed == 0 and warnings and "neobsahuje" in warnings[0]:
        return JsonResponse({"ok": False, "error": warnings[0]}, status=400)
    return JsonResponse({"ok": True, "changed": changed, "order": order, "warnings": warnings})
