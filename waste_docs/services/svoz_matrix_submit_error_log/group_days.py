"""Seskupení řádků Log SD podle kalendářního dne."""

from __future__ import annotations

from collections import OrderedDict
from datetime import date

from django.utils import timezone

CZECH_WEEKDAYS = (
    "pondělí",
    "úterý",
    "středa",
    "čtvrtek",
    "pátek",
    "sobota",
    "neděle",
)


def format_day_label(day: date) -> str:
    weekday = CZECH_WEEKDAYS[day.weekday()]
    return f"{weekday} {day.day}. {day.month}. {day.year}"


def attach_day_fields(row: dict) -> dict:
    dt = row.get("sort_at")
    if dt is None:
        row["day_iso"] = ""
        row["day_label"] = ""
        return row
    local_dt = timezone.localtime(dt)
    day = local_dt.date()
    row["day_iso"] = day.isoformat()
    row["day_label"] = format_day_label(day)
    return row


def group_rows_by_day(rows: list[dict]) -> list[dict]:
    by_day: OrderedDict[str, dict] = OrderedDict()
    for row in rows:
        attach_day_fields(row)
        key = row.get("day_iso") or ""
        if key not in by_day:
            by_day[key] = {
                "day_iso": key,
                "day_label": row.get("day_label") or "—",
                "rows": [],
            }
        by_day[key]["rows"].append(row)
    return list(by_day.values())
