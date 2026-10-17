from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from users.services.access import can_see_all_waste_docs
from waste_docs.models import Pruvodka
from waste_docs.services.print_bundle_prepare import prepare_print_bundle_files
from waste_docs.services.ride_print_order import order_rides_queryset
from waste_docs.views.dashboard_bulk import _parse_date_or_404
from waste_docs.services.ride_print_bundle_urls import ride_print_bundle_url


def _parse_vehicle_rz_id(raw: str) -> int:
    try:
        return int((raw or "").strip())
    except (TypeError, ValueError):
        return 0


def _parse_filter_pks(raw: str) -> list[int]:
    pks_raw = (raw or "").strip()
    if not pks_raw:
        return []
    try:
        return [int(p) for p in pks_raw.split(",") if p.strip().isdigit()]
    except ValueError:
        return []


def _parse_pks_list(raw: str) -> list[int]:
    pks = _parse_filter_pks(raw)
    if not pks:
        raise Http404("Neplatný parametr pks.")
    return pks


def _apply_prepare_messages(request, result: dict[str, object]) -> None:
    excel_generated = int(result.get("excel_generated") or 0)
    zpo_generated = int(result.get("zpo_generated") or 0)
    zpo_warnings = list(result.get("zpo_warnings") or [])
    parts: list[str] = []
    if excel_generated:
        parts.append(f"průvodek: {excel_generated}")
    if zpo_generated:
        parts.append(f"ZPO: {zpo_generated}")
    if parts:
        messages.success(request, f"Vygenerováno — {', '.join(parts)}.")
    if zpo_warnings:
        preview = ", ".join(zpo_warnings[:8])
        extra = f" (+{len(zpo_warnings) - 8} dalších)" if len(zpo_warnings) > 8 else ""
        messages.warning(
            request,
            f"ZPO s číslem jízdy se nepodařilo vygenerovat u: {preview}{extra}.",
        )


def _rides_for_bundle_prepare(
    request,
    *,
    selected_date: date,
    vehicle_rz_id: int,
    filter_pks: list[int],
) -> list[Pruvodka]:
    rides_qs = order_rides_queryset(
        Pruvodka.objects.filter(
            drive_date=selected_date,
            vehicle_rz_id=vehicle_rz_id,
            is_archived=False,
        ).select_related("activity")
    )
    if filter_pks:
        rides_qs = rides_qs.filter(pk__in=filter_pks)
    if not can_see_all_waste_docs(request.user):
        rides_qs = rides_qs.filter(created_by=request.user)
    rides = list(rides_qs)
    if not rides:
        raise Http404("Žádné jízdy k tisku.")
    return rides


@login_required
@require_POST
def ride_print_bundle_prepare(request):
    selected_date = _parse_date_or_404(request.POST.get("date") or "")
    vehicle_rz_id = _parse_vehicle_rz_id(request.POST.get("vehicle_rz_id") or "")
    if vehicle_rz_id <= 0:
        raise Http404("Neplatné vozidlo.")
    filter_pks = _parse_filter_pks(request.POST.get("pks") or "")
    return_url = (request.POST.get("next") or "").strip() or ride_print_bundle_url(
        selected_date=selected_date,
        vehicle_rz_id=vehicle_rz_id,
        filter_pks=filter_pks,
    )
    rides = _rides_for_bundle_prepare(
        request,
        selected_date=selected_date,
        vehicle_rz_id=vehicle_rz_id,
        filter_pks=filter_pks,
    )
    result = prepare_print_bundle_files(rides)
    _apply_prepare_messages(request, result)
    return redirect(return_url)


@login_required
@require_POST
def dashboard_bulk_print_prepare(request):
    selected_date = _parse_date_or_404(request.POST.get("date") or "")
    return_url = (request.POST.get("next") or "").strip() or (
        f"{reverse('waste_docs:dashboard_bulk_print')}?date={selected_date.isoformat()}"
    )
    from waste_docs.services.ride_bulk_actions import rides_for_day

    rides = rides_for_day(selected_date, request.user)
    if not rides:
        messages.warning(request, "Pro vybraný den nejsou dostupné žádné jízdy.")
        return redirect(f"{reverse('core:dashboard')}?date={selected_date.isoformat()}")
    result = prepare_print_bundle_files(rides)
    _apply_prepare_messages(request, result)
    return redirect(return_url)


@login_required
@require_POST
def yard_print_created_prepare(request):
    pks = _parse_pks_list(request.POST.get("pks") or "")
    return_url = (request.POST.get("next") or "").strip() or (
        f"{reverse('waste_docs:yard_print_created')}?pks={','.join(str(p) for p in pks)}"
    )
    rides = list(
        order_rides_queryset(
            Pruvodka.objects.filter(pk__in=pks, is_archived=False).select_related("activity")
        )
    )
    if not rides:
        messages.warning(request, "Žádné jízdy k tisku.")
        return redirect(reverse("waste_docs:yard_hub"))
    result = prepare_print_bundle_files(rides)
    _apply_prepare_messages(request, result)
    return redirect(return_url)


@login_required
@require_POST
def blank_pruvodka_print_prepare(request):
    from waste_docs.services.blank_pruvodka.print_bundle import parse_blank_print_pks, rides_for_blank_print

    pks = parse_blank_print_pks(
        pks_raw=request.POST.get("pks") or "",
        pk_raw="",
    )
    if not pks:
        raise Http404("Chybí parametr pks.")
    return_url = (request.POST.get("next") or "").strip() or (
        f"{reverse('waste_docs:blank_pruvodka_print')}?pks={','.join(str(p) for p in pks)}"
    )
    rides = rides_for_blank_print(pks, request.user)
    if not rides:
        messages.warning(request, "Bianko průvodky k tisku nejsou dostupné.")
        return redirect(reverse("core:dashboard"))
    result = prepare_print_bundle_files(rides, include_zpo=False)
    _apply_prepare_messages(request, result)
    return redirect(return_url)
