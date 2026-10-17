"""Stav uzávěrky druhů vozidel pro zvolené datum (JSON pro formulář požadavku)."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from customer_requests.models import CustomerRequestVehicleKindClosure
from waste_docs.services.customer_request_date_closure import is_target_date_closed


@login_required
@require_GET
def customer_request_kind_closure_status(request):
    date_raw = (request.GET.get("date") or "").strip()
    try:
        day = date.fromisoformat(date_raw)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Neplatné datum."}, status=400)

    closed_ids = list(
        CustomerRequestVehicleKindClosure.objects.filter(
            closure_date=day,
            is_closed=True,
        )
        .order_by("vehicle_kind_id")
        .values_list("vehicle_kind_id", flat=True)
    )
    return JsonResponse(
        {
            "ok": True,
            "date": day.isoformat(),
            "day_closed": is_target_date_closed(day),
            "closed_kind_ids": [int(pk) for pk in closed_ids],
        }
    )
