from __future__ import annotations

from dataclasses import dataclass, field

from django.db.models import Count
from django.utils import timezone

from reports.services.date_range import ReportDateRange
from waste_docs.models import SvozTask


@dataclass(frozen=True)
class SvozSummaryRow:
    label: str
    count: int
    share_pct: float


@dataclass
class SvozSummary:
    total: int = 0
    open_count: int = 0
    done_count: int = 0
    unresolved_without_pruvodka: int = 0
    completion_with_pruvodka_pct: float = 0.0
    avg_days_to_resolve: float | None = None
    by_yard: list[SvozSummaryRow] = field(default_factory=list)
    by_vehicle_kind: list[SvozSummaryRow] = field(default_factory=list)
    by_activity: list[SvozSummaryRow] = field(default_factory=list)


def _rows_with_share(rows: list[tuple[str, int]], total: int, *, limit: int | None = None) -> list[SvozSummaryRow]:
    out: list[SvozSummaryRow] = []
    for label, count in rows[: limit or len(rows)]:
        share = round(100.0 * count / total, 1) if total else 0.0
        out.append(SvozSummaryRow(label=label or "—", count=count, share_pct=share))
    return out


def build_svoz_summary(date_range: ReportDateRange) -> SvozSummary:
    qs = SvozTask.objects.filter(
        target_date__gte=date_range.date_from,
        target_date__lte=date_range.date_to,
    )
    total = qs.count()
    done_count = qs.filter(status=SvozTask.Status.DONE).count()
    done_with_pruvodka = qs.filter(
        status=SvozTask.Status.DONE,
        resolved_pruvodka_id__isnull=False,
    ).count()
    completion_pct = round(100.0 * done_with_pruvodka / done_count, 1) if done_count else 0.0

    avg_days: float | None = None
    done_with_ride = qs.filter(
        status=SvozTask.Status.DONE,
        resolved_pruvodka_id__isnull=False,
    ).select_related("resolved_pruvodka")
    day_diffs: list[int] = []
    for task in done_with_ride.only("target_date", "resolved_pruvodka__drive_date"):
        if task.resolved_pruvodka_id and task.resolved_pruvodka:
            day_diffs.append((task.resolved_pruvodka.drive_date - task.target_date).days)
    if day_diffs:
        avg_days = round(sum(day_diffs) / len(day_diffs), 1)

    summary = SvozSummary(
        total=total,
        open_count=qs.filter(status=SvozTask.Status.OPEN).count(),
        done_count=done_count,
        completion_with_pruvodka_pct=completion_pct,
        avg_days_to_resolve=avg_days,
    )

    today = timezone.localdate()
    summary.unresolved_without_pruvodka = SvozTask.objects.filter(
        status=SvozTask.Status.OPEN,
        resolved_pruvodka__isnull=True,
        target_date__lte=today,
    ).count()

    by_yard_raw = [
        (row.get("subject_profile__name__value") or f"Subjekt #{row['subject_profile_id']}", row["count"])
        for row in (
            qs.values("subject_profile_id", "subject_profile__name__value")
            .annotate(count=Count("id"))
            .order_by("-count")[:15]
        )
    ]
    summary.by_yard = _rows_with_share(by_yard_raw, total, limit=15)

    by_vk_raw = [
        (row.get("vehicle_kind__name") or "Bez druhu vozidla", row["count"])
        for row in qs.values("vehicle_kind__name").annotate(count=Count("id")).order_by("-count")[:15]
    ]
    summary.by_vehicle_kind = _rows_with_share(by_vk_raw, total, limit=15)

    by_activity_raw = [
        (row.get("activity__name") or "Bez činnosti", row["count"])
        for row in qs.values("activity__name").annotate(count=Count("id")).order_by("-count")[:15]
    ]
    summary.by_activity = _rows_with_share(by_activity_raw, total, limit=15)

    return summary
