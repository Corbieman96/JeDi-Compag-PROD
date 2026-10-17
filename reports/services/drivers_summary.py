from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Count

from catalogs.models import DriverAbsence
from catalogs.services.driver_absence_display import format_absence_date_range
from reports.services.date_range import ReportDateRange
from reports.services.drivers_day_rz import DriversDayRzRow, build_drivers_day_rz_rows
from reports.services.popelar_cost import PopelarCostSummary, build_popelar_cost
from waste_docs.models import Pruvodka


@dataclass(frozen=True)
class DriversSummaryRow:
    label: str
    count: int
    share_pct: float = 0.0


@dataclass(frozen=True)
class DriversOtherAbsenceRow:
    driver_label: str
    range_label: str
    days: int
    note: str


def _empty_popelar() -> PopelarCostSummary:
    zero = Decimal("0.00")
    return PopelarCostSummary(
        days=zero,
        hours=zero,
        hours_per_day=Decimal("8.00"),
        rate_czk=zero,
        total_czk=zero,
    )


@dataclass
class DriversSummary:
    total_rides: int = 0
    driver_completed_count: int = 0
    avg_rides_per_driver_day: float = 0.0
    drivers_with_absence_and_rides: int = 0
    rides_by_driver: list[DriversSummaryRow] = field(default_factory=list)
    absences_by_type: list[DriversSummaryRow] = field(default_factory=list)
    absences_by_driver: list[DriversSummaryRow] = field(default_factory=list)
    absences_other: list[DriversOtherAbsenceRow] = field(default_factory=list)
    day_rz_rows: list[DriversDayRzRow] = field(default_factory=list)
    popelar: PopelarCostSummary = field(default_factory=_empty_popelar)


def _rows_with_share(rows: list[tuple[str, int]], total: int, *, limit: int | None = None) -> list[DriversSummaryRow]:
    out: list[DriversSummaryRow] = []
    for label, count in rows[: limit or len(rows)]:
        share = round(100.0 * count / total, 1) if total else 0.0
        out.append(DriversSummaryRow(label=label or "—", count=count, share_pct=share))
    return out


def _driver_label(row: dict) -> str:
    return (
        " ".join(
            p
            for p in [
                row.get("driver__last_name") or "",
                row.get("driver__first_name") or "",
            ]
            if p
        ).strip()
        or row.get("driver__personal_number")
        or "—"
    )


def _absence_days_in_range(absence: DriverAbsence, date_range: ReportDateRange) -> int:
    start = max(absence.date_from, date_range.date_from)
    end = min(absence.date_to, date_range.date_to)
    if end < start:
        return 0
    return (end - start).days + 1


def build_drivers_summary(date_range: ReportDateRange) -> DriversSummary:
    qs = Pruvodka.objects.filter(
        drive_date__gte=date_range.date_from,
        drive_date__lte=date_range.date_to,
        driver__isnull=False,
    )
    total = qs.count()
    summary = DriversSummary(
        total_rides=total,
        driver_completed_count=qs.filter(driver_completed_at__isnull=False).count(),
    )

    driver_day_rows = list(
        qs.values("driver_id").annotate(
            ride_count=Count("id"),
            day_count=Count("drive_date", distinct=True),
        )
    )
    total_driver_days = sum(row["day_count"] for row in driver_day_rows)
    if total_driver_days:
        summary.avg_rides_per_driver_day = round(total / total_driver_days, 2)

    rides_raw = [
        (_driver_label(row), row["count"])
        for row in (
            qs.values("driver__last_name", "driver__first_name", "driver__personal_number")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
    ]
    summary.rides_by_driver = _rows_with_share(rides_raw, total)

    abs_qs = DriverAbsence.objects.filter(
        date_from__lte=date_range.date_to,
        date_to__gte=date_range.date_from,
    ).select_related("driver")
    type_labels = dict(DriverAbsence.AbsenceType.choices)
    abs_type_raw = [
        (type_labels.get(row["absence_type"], row["absence_type"]), row["count"])
        for row in abs_qs.values("absence_type").annotate(count=Count("id")).order_by("-count")
    ]
    abs_total = sum(c for _, c in abs_type_raw)
    summary.absences_by_type = _rows_with_share(abs_type_raw, abs_total)

    driver_absence_days: dict[tuple[int, str], tuple[str, int, int]] = {}
    for absence in abs_qs:
        driver_id = absence.driver_id
        if driver_id is None:
            continue
        driver_name = _driver_label(
            {
                "driver__last_name": absence.driver.last_name,
                "driver__first_name": absence.driver.first_name,
                "driver__personal_number": absence.driver.personal_number,
            }
        )
        absence_type = absence.absence_type
        type_label = type_labels.get(absence_type, absence_type)
        days = _absence_days_in_range(absence, date_range)
        key = (driver_id, absence_type)
        if key not in driver_absence_days:
            driver_absence_days[key] = (f"{driver_name} — {type_label}", 0, 0)
        prev_label, records, total_days = driver_absence_days[key]
        driver_absence_days[key] = (prev_label, records + 1, total_days + days)

    abs_driver_raw = [
        (f"{label} — {total_days} dní", records)
        for _key, (label, records, total_days) in sorted(
            driver_absence_days.items(),
            key=lambda item: item[1][2],
            reverse=True,
        )[:40]
    ]
    summary.absences_by_driver = _rows_with_share(abs_driver_raw, abs_total, limit=40)

    other_rows: list[DriversOtherAbsenceRow] = []
    for absence in abs_qs:
        if absence.absence_type != DriverAbsence.AbsenceType.OTHER:
            continue
        if absence.driver_id is None:
            continue
        days = _absence_days_in_range(absence, date_range)
        if days <= 0:
            continue
        driver_name = _driver_label(
            {
                "driver__last_name": absence.driver.last_name,
                "driver__first_name": absence.driver.first_name,
                "driver__personal_number": absence.driver.personal_number,
            }
        )
        other_rows.append(
            DriversOtherAbsenceRow(
                driver_label=driver_name,
                range_label=format_absence_date_range(absence.date_from, absence.date_to),
                days=days,
                note=(absence.note or "").strip(),
            )
        )
    other_rows.sort(key=lambda r: (r.driver_label.casefold(), r.range_label))
    summary.absences_other = other_rows

    ride_driver_ids = set(qs.values_list("driver_id", flat=True))
    absence_driver_ids = set(abs_qs.values_list("driver_id", flat=True))
    summary.drivers_with_absence_and_rides = len(ride_driver_ids & absence_driver_ids)
    summary.day_rz_rows = build_drivers_day_rz_rows(date_range)
    summary.popelar = build_popelar_cost(date_range)

    return summary
