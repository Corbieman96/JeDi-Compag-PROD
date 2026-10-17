from __future__ import annotations

from dataclasses import dataclass, field

from django.db.models import Count

from customer_requests.models import CustomerRequest
from reports.services.date_range import ReportDateRange, datetime_range_bounds


@dataclass(frozen=True)
class CustomerRequestsSummaryRow:
    label: str
    count: int
    share_pct: float = 0.0


@dataclass
class CustomerRequestsSummary:
    created_in_period: int = 0
    invoice_queue_count: int = 0
    planned_in_period: int = 0
    done_in_period: int = 0
    with_follow_up_count: int = 0
    conversion_to_ride_pct: float = 0.0
    avg_days_to_plan: float | None = None
    by_status: list[CustomerRequestsSummaryRow] = field(default_factory=list)
    by_status_all: list[CustomerRequestsSummaryRow] = field(default_factory=list)
    by_activity: list[CustomerRequestsSummaryRow] = field(default_factory=list)
    by_vehicle_kind: list[CustomerRequestsSummaryRow] = field(default_factory=list)


def _rows_with_share(rows: list[tuple[str, int]], total: int) -> list[CustomerRequestsSummaryRow]:
    out: list[CustomerRequestsSummaryRow] = []
    for label, count in rows:
        share = round(100.0 * count / total, 1) if total else 0.0
        out.append(CustomerRequestsSummaryRow(label=label or "—", count=count, share_pct=share))
    return out


def build_customer_requests_summary(date_range: ReportDateRange) -> CustomerRequestsSummary:
    start, end = datetime_range_bounds(date_range)
    created_qs = CustomerRequest.objects.filter(created_at__gte=start, created_at__lte=end)
    created_count = created_qs.count()

    status_labels = dict(CustomerRequest.Status.choices)
    by_status_raw = [
        (status_labels.get(row["status"], row["status"]), row["count"])
        for row in created_qs.values("status").annotate(count=Count("id")).order_by("-count")
    ]
    by_status = _rows_with_share(by_status_raw, created_count)

    all_qs = CustomerRequest.objects.all()
    all_total = all_qs.count()
    by_status_all_raw = [
        (status_labels.get(row["status"], row["status"]), row["count"])
        for row in all_qs.values("status").annotate(count=Count("id")).order_by("-count")
    ]
    by_status_all = _rows_with_share(by_status_all_raw, all_total)

    invoice_queue = CustomerRequest.objects.filter(
        status__in=(
            CustomerRequest.Status.SUBMITTED,
            CustomerRequest.Status.INVOICE_OVERDUE,
        )
    ).count()

    planned_in_period = created_qs.filter(
        status__in=(CustomerRequest.Status.PLANNED, CustomerRequest.Status.DONE),
        planned_pruvodka_id__isnull=False,
    ).count()
    done_in_period = created_qs.filter(status=CustomerRequest.Status.DONE).count()
    with_follow_up = created_qs.filter(has_follow_up=True).count()
    linked = created_qs.filter(planned_pruvodka_id__isnull=False).count()
    conversion_pct = round(100.0 * linked / created_count, 1) if created_count else 0.0

    avg_days: float | None = None
    deltas: list[int] = []
    for cr in (
        created_qs.filter(planned_pruvodka_id__isnull=False)
        .select_related("planned_pruvodka")
        .only("created_at", "planned_pruvodka__created_at")
    ):
        if cr.planned_pruvodka and cr.planned_pruvodka.created_at:
            delta = cr.planned_pruvodka.created_at.date() - cr.created_at.date()
            deltas.append(max(delta.days, 0))
    if deltas:
        avg_days = round(sum(deltas) / len(deltas), 1)

    by_activity_raw = [
        (row.get("activity__name") or "—", row["count"])
        for row in created_qs.values("activity__name").annotate(count=Count("id")).order_by("-count")
    ]
    by_vk_raw = [
        (row.get("vehicle_kind__name") or "Bez druhu vozidla", row["count"])
        for row in created_qs.values("vehicle_kind__name").annotate(count=Count("id")).order_by("-count")
    ]

    return CustomerRequestsSummary(
        created_in_period=created_count,
        invoice_queue_count=invoice_queue,
        planned_in_period=planned_in_period,
        done_in_period=done_in_period,
        with_follow_up_count=with_follow_up,
        conversion_to_ride_pct=conversion_pct,
        avg_days_to_plan=avg_days,
        by_status=by_status,
        by_status_all=by_status_all,
        by_activity=_rows_with_share(by_activity_raw, created_count),
        by_vehicle_kind=_rows_with_share(by_vk_raw, created_count),
    )
