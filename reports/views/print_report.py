from __future__ import annotations

from django.shortcuts import render

from reports.services.date_range import parse_date_range_from_request
from reports.services.print_summary import build_print_summary
from reports.views._common import report_context


def print_report(request):
    date_range = parse_date_range_from_request(request)
    ctx = report_context(request, date_range, title="Report: Tisk", active_slug="print")
    ctx["summary"] = build_print_summary(date_range)
    return render(request, "reports/print.html", ctx)
