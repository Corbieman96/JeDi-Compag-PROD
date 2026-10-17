from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from users.services.access import can_see_all_waste_docs
from users.services.waste_doc_permissions import can_archive_pruvodka
from waste_docs.models import Pruvodka
from waste_docs.services.blank_pruvodka import (
    BlankPruvodkaArchiveError,
    archive_blank_pruvodka,
    archive_unused_blank_for_day,
)


def _redirect_dashboard(date_iso: str) -> str:
    return f"{reverse('core:dashboard')}?date={date_iso}"


def _redirect_list(**params) -> str:
    base = reverse("waste_docs:list")
    if not params:
        return base
    qs = "&".join(f"{k}={v}" for k, v in params.items() if v)
    return f"{base}?{qs}" if qs else base


@login_required
@require_POST
def blank_pruvodka_archive(request, pk):
    if not can_archive_pruvodka(request.user):
        raise Http404("Stránka neexistuje.")

    item = get_object_or_404(Pruvodka, pk=pk, is_archived=False)
    if not can_see_all_waste_docs(request.user) and item.created_by_id != request.user.id:
        raise Http404("Jízda neexistuje.")

    date_iso = item.drive_date.isoformat()
    next_url = (request.POST.get("next") or _redirect_dashboard(date_iso)).strip()
    reason = (request.POST.get("archive_reason") or "").strip()

    try:
        archive_blank_pruvodka(pruvodka=item, user=request.user, reason=reason)
    except BlankPruvodkaArchiveError as exc:
        messages.error(request, str(exc))
        return redirect(next_url or _redirect_dashboard(date_iso))

    messages.success(request, "Bianko průvodka byla archivována.")
    return redirect(next_url or _redirect_dashboard(date_iso))


@login_required
@require_POST
def blank_pruvodka_archive_bulk(request):
    if not can_archive_pruvodka(request.user):
        raise Http404("Stránka neexistuje.")

    date_raw = (request.POST.get("drive_date") or "").strip()
    next_url = (request.POST.get("next") or "").strip()
    reason = (request.POST.get("archive_reason") or "").strip()

    try:
        drive_date = date.fromisoformat(date_raw)
    except ValueError:
        messages.error(request, "Neplatné datum.")
        return redirect(next_url or reverse("core:dashboard"))

    archived = archive_unused_blank_for_day(drive_date=drive_date, user=request.user, reason=reason)
    if archived:
        messages.success(request, f"Archivováno nepoužitých bianko průvodek: {archived}.")
    else:
        messages.info(request, "Žádné nepoužité bianko průvodky k archivaci.")
    return redirect(next_url or _redirect_dashboard(drive_date.isoformat()))
