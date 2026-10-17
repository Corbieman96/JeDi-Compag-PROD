from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from users.services.access import can_see_all_waste_docs
from waste_docs.services.ride_document_email.recipient_presets import (
    add_recipient,
    delete_recipient,
    list_recipients,
    recipient_to_dict,
)


def _require_email_recipient_access(user) -> None:
    if not user.is_authenticated or not can_see_all_waste_docs(user):
        raise Http404()


def _parse_json_body(request) -> dict:
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return request.POST


@login_required
@require_GET
def ride_email_recipients_list(request):
    _require_email_recipient_access(request.user)
    return JsonResponse({"ok": True, "recipients": list_recipients()})


@login_required
@require_POST
def ride_email_recipient_add(request):
    _require_email_recipient_access(request.user)
    payload = _parse_json_body(request)
    raw_email = payload.get("email") or request.POST.get("email") or ""
    label = payload.get("label") or request.POST.get("label") or ""
    try:
        row, created = add_recipient(raw_email, label=label, user=request.user)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse(
        {
            "ok": True,
            "created": created,
            "recipient": recipient_to_dict(row),
            "recipients": list_recipients(),
        }
    )


@login_required
@require_POST
def ride_email_recipient_delete(request, pk: int):
    _require_email_recipient_access(request.user)
    if pk <= 0:
        raise Http404()
    if not delete_recipient(pk):
        raise Http404()
    return JsonResponse({"ok": True, "recipients": list_recipients()})
