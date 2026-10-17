from __future__ import annotations

from django.shortcuts import render

from reports.services.date_range import parse_date_range_from_request
from reports.services.svoz_summary import build_svoz_summary
from reports.views._common import report_context


def svoz_report(request):
    date_range = parse_date_range_from_request(request)
    ctx = report_context(request, date_range, title="Report: Svozové úkoly", active_slug="svoz")
    ctx["summary"] = build_svoz_summary(date_range)
    return render(request, "reports/svoz.html", ctx)
