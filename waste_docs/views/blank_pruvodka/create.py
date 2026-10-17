from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from users.services.waste_doc_permissions import can_create_pruvodka
from waste_docs.services.blank_pruvodka import BlankPruvodkaCreateError, create_blank_pruvodky


@login_required
@require_POST
def blank_pruvodka_create(request):
    if not can_create_pruvodka(request.user):
        raise Http404("Stránka neexistuje.")

    date_raw = (request.POST.get("drive_date") or "").strip()
    count_raw = (request.POST.get("count") or "5").strip()
    note = (request.POST.get("note") or "").strip()

    try:
        drive_date = date.fromisoformat(date_raw)
    except ValueError as exc:
        messages.error(request, "Neplatné datum jízdy.")
        return redirect(f"{reverse('core:dashboard')}?date={date_raw or ''}")

    try:
        count = int(count_raw)
    except ValueError:
        count = 0

    try:
        created = create_blank_pruvodky(
            drive_date=drive_date,
            count=count,
            user=request.user,
            note=note,
        )
    except BlankPruvodkaCreateError as exc:
        messages.error(request, str(exc))
        return redirect(f"{reverse('core:dashboard')}?date={drive_date.isoformat()}")

    pks = ",".join(str(r.pk) for r in created)
    messages.success(request, f"Vytvořeno bianko průvodek: {len(created)}.")
    return redirect(f"{reverse('waste_docs:blank_pruvodka_print')}?pks={pks}")
