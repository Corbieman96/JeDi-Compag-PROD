"""Admin report — úplný TXT výcuc období (izolovaný panel)."""

from __future__ import annotations

from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from core.services.reports.period_txt_digest import (
    build_period_digest_txt_bytes,
    txt_attachment_response,
    user_can_period_txt_digest,
)
from reports.services.date_range import date_range_querystring, parse_date_range_from_request
from reports.views._common import ReportCard, report_context
from users.services.roles import get_user_role_label


def _require_admin(request):
    if not user_can_period_txt_digest(request.user):
        raise Http404("Výcuc období je dostupný jen pro Admin.")


def period_digest_card(date_range) -> ReportCard:
    qs = date_range_querystring(date_range)
    return ReportCard(
        slug="period_digest",
        title="Výcuc období (TXT)",
        description=(
            "Úplná textová záloha jízd, požadavků a poznámek za období "
            "(den, kde, kdo, co) — ke stažení jako .txt."
        ),
        href=f"{reverse('reports:period_digest')}?{qs}",
        kpi_hint="Jen Admin",
    )


def period_digest_page(request):
    _require_admin(request)
    date_range = parse_date_range_from_request(request)
    ctx = report_context(
        request,
        date_range,
        title="Výcuc období (TXT)",
        active_slug="period_digest",
    )
    ctx["download_url"] = (
        f"{reverse('reports:period_digest_txt')}?"
        f"date_from={date_range.date_from.isoformat()}&date_to={date_range.date_to.isoformat()}"
    )
    ctx["exporter_label"] = get_user_role_label(request.user)
    return render(request, "reports/period_digest.html", ctx)


def period_digest_txt(request):
    _require_admin(request)
    date_range = parse_date_range_from_request(request)
    exported_by = getattr(request.user, "username", "") or ""
    filename, content = build_period_digest_txt_bytes(
        date_from=date_range.date_from,
        date_to=date_range.date_to,
        exported_by=exported_by,
    )
    return txt_attachment_response(filename=filename, content=content)
