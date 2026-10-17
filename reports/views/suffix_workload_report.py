from __future__ import annotations

from django.shortcuts import render

from reports.services.date_range import parse_date_range_from_request
from reports.services.suffix_workload_summary import build_suffix_workload_summary
from reports.views._common import report_context


def suffix_workload_report(request):
    date_range = parse_date_range_from_request(request)
    ctx = report_context(
        request,
        date_range,
        title="Report: Vytížení koncovek",
        active_slug="suffix_workload",
    )
    ctx["summary"] = build_suffix_workload_summary(date_range)
    return render(request, "reports/suffix_workload.html", ctx)
