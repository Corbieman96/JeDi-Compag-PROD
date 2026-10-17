from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from users.services.waste_doc_permissions import can_purge_dashboard_day_files
from waste_docs.services.dashboard_day_purge import purge_day_generated_artifacts
from waste_docs.services.dashboard_media_purge import purge_all_generated_artifacts


def _parse_date_or_404(raw: str) -> date:
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError as exc:
        raise Http404("Neplatné datum.") from exc


@login_required
@require_POST
def dashboard_day_purge(request):
    if not can_purge_dashboard_day_files(request.user):
        raise Http404("Stránka neexistuje.")
    selected_date = _parse_date_or_404(request.POST.get("date") or "")
    dashboard_url = f"{reverse('core:dashboard')}?date={selected_date.isoformat()}"
    result = purge_day_generated_artifacts(selected_date, request.user)
    if result.total_files == 0 and result.print_marks == 0:
        messages.info(request, result.summary_message())
    else:
        messages.success(request, result.summary_message())
    return redirect(dashboard_url)


@login_required
@require_POST
def dashboard_media_purge_all(request):
    if not can_purge_dashboard_day_files(request.user):
        raise Http404("Stránka neexistuje.")
    selected_date = _parse_date_or_404(request.POST.get("date") or "")
    dashboard_url = f"{reverse('core:dashboard')}?date={selected_date.isoformat()}"
    result = purge_all_generated_artifacts()
    if result.total_files == 0 and result.print_marks == 0 and result.db_rides == 0:
        messages.info(request, result.summary_message())
    else:
        messages.success(request, result.summary_message())
    return redirect(dashboard_url)
