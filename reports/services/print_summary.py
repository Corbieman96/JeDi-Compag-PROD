from __future__ import annotations

from dataclasses import dataclass, field

from django.db.models import Count

from reports.services.date_range import ReportDateRange, datetime_range_bounds
from waste_docs.models import PrintFileMark


@dataclass(frozen=True)
class PrintSummaryRow:
    label: str
    count: int
    share_pct: float = 0.0


@dataclass
class PrintSummary:
    total_marks: int = 0
    by_user: list[PrintSummaryRow] = field(default_factory=list)
    by_drive_date: list[PrintSummaryRow] = field(default_factory=list)


def _rows_with_share(rows: list[tuple[str, int]], total: int, *, limit: int | None = None) -> list[PrintSummaryRow]:
    out: list[PrintSummaryRow] = []
    for label, count in rows[: limit or len(rows)]:
        share = round(100.0 * count / total, 1) if total else 0.0
        out.append(PrintSummaryRow(label=label or "—", count=count, share_pct=share))
    return out


def build_print_summary(date_range: ReportDateRange) -> PrintSummary:
    start, end = datetime_range_bounds(date_range)
    qs = PrintFileMark.objects.filter(printed_at__gte=start, printed_at__lte=end)
    total = qs.count()

    by_user_raw = [
        (row.get("user__username") or f"Uživatel #{row['user_id']}", row["count"])
        for row in qs.values("user_id", "user__username").annotate(count=Count("id")).order_by("-count")[:20]
    ]
    by_date_raw = [
        (row["drive_date"].strftime("%d.%m.%Y"), row["count"])
        for row in qs.values("drive_date").annotate(count=Count("id")).order_by("-drive_date")[:31]
    ]

    return PrintSummary(
        total_marks=total,
        by_user=_rows_with_share(by_user_raw, total, limit=20),
        by_drive_date=_rows_with_share(by_date_raw, total, limit=31),
    )
