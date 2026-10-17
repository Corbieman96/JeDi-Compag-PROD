from __future__ import annotations

from django.shortcuts import render

from reports.services.customer_requests_summary import build_customer_requests_summary
from reports.services.date_range import parse_date_range_from_request
from reports.views._common import report_context


def customer_requests_report(request):
    date_range = parse_date_range_from_request(request)
    ctx = report_context(
        request,
        date_range,
        title="Report: Požadavky zákazníků",
        active_slug="customer_requests",
    )
    ctx["summary"] = build_customer_requests_summary(date_range)
    return render(request, "reports/customer_requests.html", ctx)
