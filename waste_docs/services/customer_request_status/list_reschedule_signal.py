"""UI signál přeplánování jízdy pro seznam požadavků (jedna dávka na stránku)."""

from __future__ import annotations

from collections.abc import Iterable

from customer_requests.models import CustomerRequest, CustomerRequestAuditLog
from waste_docs.services.customer_request_status.align_ride_date import (
    RIDE_RESCHEDULED_AUDIT_ACTION,
    ride_rescheduled_banner_text,
)


def ride_reschedule_labels_for_page(items: Iterable[CustomerRequest]) -> dict[int, str]:
    ids = [item.pk for item in items]
    if not ids:
        return {}
    logs = CustomerRequestAuditLog.objects.filter(
        request_id__in=ids,
        action=RIDE_RESCHEDULED_AUDIT_ACTION,
    ).order_by("request_id", "-created_at", "-id")
    labels: dict[int, str] = {}
    for log in logs:
        if log.request_id in labels:
            continue
        labels[log.request_id] = ride_rescheduled_banner_text(log.note)
    return labels
