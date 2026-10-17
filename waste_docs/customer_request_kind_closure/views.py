"""Přepnutí a stav uzavření druhu vozidla pro zákaznické požadavky."""

from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from users.services.access import can_see_all_waste_docs
from waste_docs.customer_request_kind_closure.services.status import (
    customer_request_kind_closure_status,
)
from waste_docs.customer_request_kind_closure.services.toggle import toggle_vehicle_kind_closure

__all__ = [
    "customer_request_kind_closure_status",
    "customer_request_kind_closure_toggle",
]


@login_required
@require_POST
def customer_request_kind_closure_toggle(request):
    if not can_see_all_waste_docs(request.user):
        raise Http404("Stránka neexistuje.")

    date_raw = (request.POST.get("date") or "").strip()
    kind_raw = (request.POST.get("vehicle_kind_id") or "").strip()
    try:
        closure_day = date.fromisoformat(date_raw)
    except ValueError as exc:
        raise Http404("Neplatné datum.") from exc
    if not kind_raw.isdigit():
        raise Http404("Neplatný druh vozidla.")
    vehicle_kind_id = int(kind_raw)

    try:
        is_closed = toggle_vehicle_kind_closure(request.user, closure_day, vehicle_kind_id)
    except ValueError as exc:
        raise Http404(str(exc)) from exc

    from catalogs.models import VehicleKindCatalog

    kind = VehicleKindCatalog.objects.filter(pk=vehicle_kind_id).first()
    label = kind.display_label() if kind else str(vehicle_kind_id)
    day_label = closure_day.strftime("%d.%m.%Y")
    if is_closed:
        messages.success(
            request,
            f"Pro {day_label} je uzavřeno zadávání požadavků pro {label}.",
        )
    else:
        messages.success(
            request,
            f"Pro {day_label} je znovu otevřeno zadávání požadavků pro {label}.",
        )
    return redirect(f"{reverse('core:dashboard')}?date={closure_day.isoformat()}")
