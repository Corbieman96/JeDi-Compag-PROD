from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from django.http import HttpRequest
from django.utils import timezone


@dataclass(frozen=True)
class ReportDateRange:
    date_from: date
    date_to: date

    @property
    def label(self) -> str:
        return f"{self.date_from:%d.%m.%Y} – {self.date_to:%d.%m.%Y}"


def _parse_iso_date(raw: str | None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def default_report_date_range(today: date | None = None) -> ReportDateRange:
    today = today or timezone.localdate()
    date_from = today.replace(day=1)
    return ReportDateRange(date_from=date_from, date_to=today)


def parse_date_range_from_request(request: HttpRequest) -> ReportDateRange:
    """Společný filtr období z GET parametrů date_from / date_to."""
    default = default_report_date_range()
    date_from = _parse_iso_date(request.GET.get("date_from")) or default.date_from
    date_to = _parse_iso_date(request.GET.get("date_to")) or default.date_to
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    return ReportDateRange(date_from=date_from, date_to=date_to)


def date_range_querystring(date_range: ReportDateRange) -> str:
    return f"date_from={date_range.date_from.isoformat()}&date_to={date_range.date_to.isoformat()}"


def datetime_range_bounds(date_range: ReportDateRange) -> tuple[datetime, datetime]:
    """Lokální začátek/konec období pro filtry DateTimeField."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date_range.date_from, time.min), tz)
    end = timezone.make_aware(datetime.combine(date_range.date_to, time.max), tz)
    return start, end
