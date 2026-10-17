"""AJAX: ride_note páru pro formulář zákaznického požadavku."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from waste_docs.customer_request_pair_ride_note.services.lookup import lookup_pair_ride_note


def _int_or_none(raw) -> int | None:
    text = str(raw or "").strip()
    if not text.isdigit():
        return None
    return int(text)


@login_required
@require_GET
def customer_request_pair_ride_note(request):
    note = lookup_pair_ride_note(
        pair_id=_int_or_none(request.GET.get("pair_id")),
        name_id=_int_or_none(request.GET.get("name_id")),
        waste_type_id=_int_or_none(request.GET.get("waste_type_id")),
        suffix_id=_int_or_none(request.GET.get("suffix_id")),
        address=(request.GET.get("address") or "").strip(),
    )
    return JsonResponse({"ok": True, "ride_note": note})
