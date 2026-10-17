from __future__ import annotations

from django.shortcuts import render

from reports.services.date_range import parse_date_range_from_request
from reports.services.operations_summary import build_operations_summary
from reports.views._common import report_context


def operations_report(request):
    date_range = parse_date_range_from_request(request)
    ctx = report_context(request, date_range, title="Report: Provoz", active_slug="operations")
    ctx["summary"] = build_operations_summary(date_range)
    return render(request, "reports/operations.html", ctx)
