from __future__ import annotations

import json
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST

from waste_docs.services.manual_print_marks import mark_row_printed


def _parse_date_or_404(raw: str) -> date:
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError as exc:
        raise Http404("Neplatné datum.") from exc


@login_required
@require_POST
def mark_file_row_printed(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}
    drive_date = _parse_date_or_404(
        payload.get("date") or request.POST.get("date") or ""
    )
    row_key = (payload.get("row_key") or request.POST.get("row_key") or "").strip()
    if not row_key or len(row_key) > 255:
        return JsonResponse({"ok": False, "error": "Neplatný row_key."}, status=400)
    mark_row_printed(request.user, drive_date, row_key)
    return JsonResponse({"ok": True})
