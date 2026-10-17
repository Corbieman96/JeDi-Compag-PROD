from __future__ import annotations

from dataclasses import dataclass, field

from django.db.models import Count

from reports.services.date_range import ReportDateRange
from waste_docs.models import Pruvodka


@dataclass(frozen=True)
class SuffixWorkloadRow:
    label: str
    count: int
    share_pct: float = 0.0


@dataclass
class SuffixGroupSection:
    """Skupina (vozidlo, druh odpadu…) s rozpadením na koncovky."""

    title: str
    total_rides: int
    suffix_rows: list[SuffixWorkloadRow] = field(default_factory=list)


@dataclass
class SuffixWorkloadSummary:
    total: int = 0
    by_suffix: list[SuffixWorkloadRow] = field(default_factory=list)
    by_vehicle_rz_overview: list[SuffixWorkloadRow] = field(default_factory=list)
    by_vehicle: list[SuffixGroupSection] = field(default_factory=list)
    by_waste_type: list[SuffixGroupSection] = field(default_factory=list)
    by_suffix_waste_type: list[SuffixWorkloadRow] = field(default_factory=list)


def _label_or_dash(value: str | None, *, fallback: str = "—") -> str:
    text = (value or "").strip()
    return text or fallback


def _rows_with_share(rows: list[tuple[str, int]], total: int, *, limit: int | None = None) -> list[SuffixWorkloadRow]:
    out: list[SuffixWorkloadRow] = []
    for label, count in rows[: limit or len(rows)]:
        share = round(100.0 * count / total, 1) if total else 0.0
        out.append(SuffixWorkloadRow(label=label or "—", count=count, share_pct=share))
    return out


def _aggregate_field(qs, field_name: str, total: int, *, limit: int | None = None) -> list[SuffixWorkloadRow]:
    raw = [
        (_label_or_dash(row.get(field_name), fallback="Bez údaje"), row["count"])
        for row in qs.values(field_name).annotate(count=Count("id")).order_by("-count")
    ]
    return _rows_with_share(raw, total, limit=limit)


def _group_suffix_by_dimension(qs, dimension_field: str, *, title_prefix: str) -> list[SuffixGroupSection]:
    combo_rows = list(
        qs.values(dimension_field, "suffix_snapshot")
        .annotate(count=Count("id"))
        .order_by(dimension_field, "-count")
    )
    grouped: dict[str, list[tuple[str, int]]] = {}
    totals: dict[str, int] = {}
    for row in combo_rows:
        group_key = _label_or_dash(row.get(dimension_field), fallback="Bez údaje")
        suffix = _label_or_dash(row.get("suffix_snapshot"))
        count = row["count"]
        grouped.setdefault(group_key, []).append((suffix, count))
        totals[group_key] = totals.get(group_key, 0) + count

    sections: list[SuffixGroupSection] = []
    for group_key in sorted(grouped.keys(), key=lambda key: totals[key], reverse=True):
        group_total = totals[group_key]
        sections.append(
            SuffixGroupSection(
                title=f"{title_prefix} {group_key}",
                total_rides=group_total,
                suffix_rows=_rows_with_share(grouped[group_key], group_total),
            )
        )
    return sections


def build_suffix_workload_summary(date_range: ReportDateRange) -> SuffixWorkloadSummary:
    qs = Pruvodka.objects.filter(
        drive_date__gte=date_range.date_from,
        drive_date__lte=date_range.date_to,
        is_archived=False,
    )
    total = qs.count()
    summary = SuffixWorkloadSummary(total=total)

    summary.by_suffix = _aggregate_field(qs, "suffix_snapshot", total)
    summary.by_vehicle_rz_overview = _aggregate_field(qs, "vehicle_rz_snapshot", total)
    summary.by_vehicle = _group_suffix_by_dimension(qs, "vehicle_rz_snapshot", title_prefix="Vozidlo")
    summary.by_waste_type = _group_suffix_by_dimension(qs, "waste_type_snapshot", title_prefix="Druh odpadu")

    suffix_waste_raw = [
        (
            f"{_label_or_dash(row.get('suffix_snapshot'))} / {_label_or_dash(row.get('waste_type_snapshot'))}",
            row["count"],
        )
        for row in (
            qs.values("suffix_snapshot", "waste_type_snapshot")
            .annotate(count=Count("id"))
            .order_by("-count")[:25]
        )
    ]
    summary.by_suffix_waste_type = _rows_with_share(suffix_waste_raw, total, limit=25)

    return summary
