from __future__ import annotations

from reports.services.date_range import parse_date_range_from_request
from reports.services.drivers_summary import build_drivers_summary
from reports.services.exports.drivers_export import build_drivers_xlsx_bytes
from reports.services.exports.http import xlsx_attachment_response


def drivers_export_xlsx(request):
    date_range = parse_date_range_from_request(request)
    summary = build_drivers_summary(date_range)
    payload, filename = build_drivers_xlsx_bytes(summary, date_range)
    return xlsx_attachment_response(payload, filename)
