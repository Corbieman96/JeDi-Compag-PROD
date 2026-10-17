from __future__ import annotations

from django.shortcuts import render

from reports.services.date_range import parse_date_range_from_request
from reports.services.drivers_summary import build_drivers_summary
from reports.views._common import report_context


def drivers_report(request):
    date_range = parse_date_range_from_request(request)
    ctx = report_context(request, date_range, title="Report: Řidiči", active_slug="drivers")
    ctx["summary"] = build_drivers_summary(date_range)
    return render(request, "reports/drivers.html", ctx)
