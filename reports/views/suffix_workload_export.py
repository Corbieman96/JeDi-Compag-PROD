from __future__ import annotations

from django.contrib.auth.decorators import login_required

from reports.services.date_range import parse_date_range_from_request
from reports.services.exports.http import xlsx_attachment_response
from reports.services.exports.suffix_workload_export import build_suffix_workload_xlsx_bytes
from reports.services.suffix_workload_summary import build_suffix_workload_summary
from users.decorators import reports_nav_required


@login_required
@reports_nav_required
def suffix_workload_export_xlsx(request):
    date_range = parse_date_range_from_request(request)
    summary = build_suffix_workload_summary(date_range)
    payload, filename = build_suffix_workload_xlsx_bytes(summary, date_range)
    return xlsx_attachment_response(payload, filename)
