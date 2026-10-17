"""Dispečer — správa chybového logu odeslání matice (mazání, ack, stažení .txt)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_GET, require_POST

from catalogs.models import NameSubjectProfile
from users.services.access import can_see_all_waste_docs
from waste_docs.models.yard_svoz_submit_error_log import YardSvozSubmitErrorLog
from waste_docs.services.svoz_matrix_submit_error_log import (
    acknowledge_unread,
    build_txt_bytes,
    delete_row,
    delete_rows_for_subject,
    delete_selected,
    dispatcher_error_log_dashboard,
)
from waste_docs.services.svoz_matrix_submit_error_log.dashboard import (
    DASHBOARD_MODAL_ROW_LIMIT,
)
from waste_docs.services.svoz_matrix_submit_error_log.yard_choices import (
    collection_yard_choices,
    collection_yard_or_none,
    yard_display_label,
)


def _require_dispatcher(user) -> None:
    if not can_see_all_waste_docs(user):
        raise Http404("Chybový log svozu není k dispozici.")


def _dashboard_redirect(request: HttpRequest) -> HttpResponse:
    date = (request.POST.get("date") or request.GET.get("date") or "").strip()
    url = reverse("core:dashboard")
    q = []
    if date:
        q.append(f"date={date}")
    q.append("svoz_error_log=1")
    return redirect(url + "?" + "&".join(q))


def _log_page_url(*, subject_id: int | None = None) -> str:
    url = reverse("waste_docs:svoz_submit_error_log")
    if subject_id:
        return f"{url}?subject={int(subject_id)}"
    return url


def _after_manage_redirect(request: HttpRequest) -> HttpResponse:
    if (request.POST.get("next") or "").strip() == "log":
        raw = (request.POST.get("subject") or "").strip()
        subject_id = int(raw) if raw.isdigit() else None
        return redirect(_log_page_url(subject_id=subject_id))
    return _dashboard_redirect(request)


def _parse_subject_id(request: HttpRequest) -> int | None:
    raw = (request.GET.get("subject") or "").strip()
    return int(raw) if raw.isdigit() else None


@login_required
@require_GET
def svoz_submit_error_log(request: HttpRequest) -> HttpResponse:
    _require_dispatcher(request.user)
    selected = collection_yard_or_none(subject_id=_parse_subject_id(request))
    selected_id = selected.pk if selected else None
    ctx = dispatcher_error_log_dashboard(
        subject_profile_id=selected_id,
        include_login=True,
    )
    if selected_id is None:
        ctx["yard_submit_error_groups"] = []
    elif not ctx["yard_submit_error_groups"]:
        ctx["yard_submit_error_groups"] = [
            {
                "subject_id": selected.pk,
                "subject_label": yard_display_label(selected),
                "rows": [],
                "days": [],
                "unread_count": 0,
            }
        ]
    ctx["error_log_return"] = "log"
    ctx["yard_log_choices"] = collection_yard_choices()
    ctx["selected_subject_id"] = selected_id
    return render(request, "waste_docs/svoz_submit_error_log.html", ctx)


@login_required
@require_GET
def svoz_submit_error_log_modal_partial(request: HttpRequest) -> HttpResponse:
    """HTML skupin logu pro modal dashboardu — načte se až při otevření."""
    _require_dispatcher(request.user)
    ctx = dispatcher_error_log_dashboard(row_limit=DASHBOARD_MODAL_ROW_LIMIT)
    ctx["selected_date_iso"] = (request.GET.get("date") or "").strip()
    return render(request, "waste_docs/partials/svoz_submit_error_log_groups.html", ctx)


@login_required
@require_POST
def svoz_submit_error_log_delete_row(request: HttpRequest, pk: int) -> HttpResponse:
    _require_dispatcher(request.user)
    get_object_or_404(YardSvozSubmitErrorLog, pk=pk)
    delete_row(pk=pk)
    messages.success(request, "Řádek chybového logu byl smazán.")
    return _after_manage_redirect(request)


@login_required
@require_POST
def svoz_submit_error_log_delete_yard(request: HttpRequest, subject_pk: int) -> HttpResponse:
    _require_dispatcher(request.user)
    get_object_or_404(NameSubjectProfile, pk=subject_pk)
    n = delete_rows_for_subject(subject_profile_id=subject_pk)
    messages.success(request, f"Smazáno {n} záznamů chybového logu dvora.")
    return _after_manage_redirect(request)


@login_required
@require_POST
def svoz_submit_error_log_delete_selected(request: HttpRequest, subject_pk: int) -> HttpResponse:
    _require_dispatcher(request.user)
    get_object_or_404(NameSubjectProfile, pk=subject_pk)
    n = delete_selected(
        subject_profile_id=subject_pk,
        error_pks=request.POST.getlist("error"),
        sent_pks=request.POST.getlist("sent"),
        day_isos=request.POST.getlist("day"),
    )
    if n:
        messages.success(request, f"Smazáno {n} záznamů z logu.")
    else:
        messages.warning(request, "Nevybrali jste žádné dny ani záznamy ke smazání.")
    return _after_manage_redirect(request)


@login_required
@require_POST
def svoz_submit_error_log_acknowledge(request: HttpRequest) -> HttpResponse:
    _require_dispatcher(request.user)
    acknowledge_unread(user=request.user)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    messages.success(request, "Chyby sběrných dvorů jsou označené jako přečtené.")
    return _after_manage_redirect(request)


@login_required
@require_GET
def svoz_submit_error_log_txt(request: HttpRequest, subject_pk: int) -> HttpResponse:
    _require_dispatcher(request.user)
    get_object_or_404(NameSubjectProfile, pk=subject_pk)
    stem, data = build_txt_bytes(subject_profile_id=subject_pk)
    resp = HttpResponse(data, content_type="text/plain; charset=utf-8")
    resp["Content-Disposition"] = content_disposition_header(
        as_attachment=True,
        filename=f"svoz_chyby_{stem}.txt",
    )
    return resp
