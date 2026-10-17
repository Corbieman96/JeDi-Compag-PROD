from __future__ import annotations

from django.shortcuts import render

from reports.services.date_range import parse_date_range_from_request
from reports.services.rides_summary import build_rides_summary
from reports.views._common import report_context


def rides_report(request):
    date_range = parse_date_range_from_request(request)
    ctx = report_context(request, date_range, title="Report: Jízdy", active_slug="rides")
    ctx["summary"] = build_rides_summary(date_range)
    return render(request, "reports/rides.html", ctx)
