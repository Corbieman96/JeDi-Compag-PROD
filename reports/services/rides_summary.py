from __future__ import annotations

from dataclasses import dataclass, field

from django.db.models import Count, Q

from reports.services.date_range import ReportDateRange
from waste_docs.models import Pruvodka


@dataclass(frozen=True)
class RidesSummaryRow:
    label: str
    count: int
    share_pct: float


@dataclass
class RidesSummary:
    total: int = 0
    archived_count: int = 0
    driver_completed_count: int = 0
    generated_count: int = 0
    generated_pct: float = 0.0
    zpo_generated_count: int = 0
    follow_up_open_count: int = 0
    follow_up_child_count: int = 0
    without_driver_count: int = 0
    without_rz_count: int = 0
    blank_pruvodka_count: int = 0
    from_customer_request_count: int = 0
    with_container_passport_count: int = 0
    by_status: list[RidesSummaryRow] = field(default_factory=list)
    by_day: list[RidesSummaryRow] = field(default_factory=list)
    by_activity: list[RidesSummaryRow] = field(default_factory=list)
    by_vehicle_kind: list[RidesSummaryRow] = field(default_factory=list)
    top_drivers: list[RidesSummaryRow] = field(default_factory=list)
    top_vehicle_rz: list[RidesSummaryRow] = field(default_factory=list)
    top_subjects: list[RidesSummaryRow] = field(default_factory=list)


def _rows_with_share(rows: list[tuple[str, int]], total: int, *, limit: int | None = None) -> list[RidesSummaryRow]:
    out: list[RidesSummaryRow] = []
    for label, count in rows[: limit or len(rows)]:
        share = round(100.0 * count / total, 1) if total else 0.0
        out.append(RidesSummaryRow(label=label or "—", count=count, share_pct=share))
    return out


def _vehicle_kind_label(row: dict) -> str:
    name = (row.get("vehicle_rz__profile__vehicle_kinds__name") or "").strip()
    shortcut = (row.get("vehicle_rz__profile__vehicle_kinds__shortcut") or "").strip()
    if name and shortcut:
        return f"{name} ({shortcut})"
    return name or shortcut or "Bez druhu vozidla"


def build_rides_summary(date_range: ReportDateRange) -> RidesSummary:
    qs = Pruvodka.objects.filter(
        drive_date__gte=date_range.date_from,
        drive_date__lte=date_range.date_to,
    )
    total = qs.count()
    generated_count = qs.filter(status=Pruvodka.Status.GENERATED).count()
    summary = RidesSummary(
        total=total,
        archived_count=qs.filter(is_archived=True).count(),
        driver_completed_count=qs.filter(driver_completed_at__isnull=False).count(),
        generated_count=generated_count,
        generated_pct=round(100.0 * generated_count / total, 1) if total else 0.0,
        zpo_generated_count=qs.exclude(Q(zpo_instance_file="") | Q(zpo_instance_file__isnull=True)).count(),
        follow_up_open_count=qs.filter(follow_up_open=True).count(),
        follow_up_child_count=qs.filter(follow_up_parent_id__isnull=False).count(),
        without_driver_count=qs.filter(driver_id__isnull=True).count(),
        without_rz_count=qs.filter(vehicle_rz_id__isnull=True).count(),
        blank_pruvodka_count=qs.filter(is_blank_pruvodka=True).count(),
        from_customer_request_count=qs.filter(customer_requests_primary__isnull=False).distinct().count(),
        with_container_passport_count=qs.filter(container_passport_id__isnull=False).count(),
    )

    status_labels = dict(Pruvodka.Status.choices)
    by_status_raw = [
        (status_labels.get(row["status"], row["status"]), row["count"])
        for row in qs.values("status").annotate(count=Count("id")).order_by("-count")
    ]
    summary.by_status = _rows_with_share(by_status_raw, total)

    by_day_raw = [
        (row["drive_date"].strftime("%d.%m.%Y"), row["count"])
        for row in qs.values("drive_date").annotate(count=Count("id")).order_by("drive_date")
    ]
    summary.by_day = _rows_with_share(by_day_raw, total)

    by_activity_raw = [
        ((row.get("activity_snapshot") or "").strip() or "Bez činnosti", row["count"])
        for row in (
            qs.values("activity_snapshot")
            .annotate(count=Count("id"))
            .order_by("-count")[:15]
        )
    ]
    summary.by_activity = _rows_with_share(by_activity_raw, total, limit=15)

    by_vk_raw = [
        (_vehicle_kind_label(row), row["count"])
        for row in (
            qs.filter(vehicle_rz_id__isnull=False)
            .values(
                "vehicle_rz__profile__vehicle_kinds__name",
                "vehicle_rz__profile__vehicle_kinds__shortcut",
            )
            .annotate(count=Count("id", distinct=True))
            .order_by("-count")[:15]
        )
    ]
    summary.by_vehicle_kind = _rows_with_share(by_vk_raw, total, limit=15)

    top_drivers_raw = [
        (
            " ".join(
                p
                for p in [
                    row.get("driver__last_name") or "",
                    row.get("driver__first_name") or "",
                ]
                if p
            ).strip()
            or row.get("driver__personal_number")
            or "Bez řidiče",
            row["count"],
        )
        for row in (
            qs.values("driver__last_name", "driver__first_name", "driver__personal_number")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )
    ]
    summary.top_drivers = _rows_with_share(top_drivers_raw, total, limit=10)

    top_rz_raw = [
        (row.get("vehicle_rz__value") or "Bez RZ", row["count"])
        for row in qs.values("vehicle_rz__value").annotate(count=Count("id")).order_by("-count")[:10]
    ]
    summary.top_vehicle_rz = _rows_with_share(top_rz_raw, total, limit=10)

    top_subjects_raw = [
        (row.get("name__value") or "—", row["count"])
        for row in qs.values("name__value").annotate(count=Count("id")).order_by("-count")[:10]
    ]
    summary.top_subjects = _rows_with_share(top_subjects_raw, total, limit=10)

    return summary
