"""Časová okna pro odložené odeslání matice sběrného dvora."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.utils import timezone

DEFER_WINDOW_START = time(11, 0)
DEFER_WINDOW_END = time(13, 0)
PROCESS_AFTER_TIME = time(17, 0)


def is_deferred_svoz_matrix_window(*, now: datetime | None = None) -> bool:
    """True pokud je lokální čas v intervalu [11:00, 13:00)."""
    local = timezone.localtime(now or timezone.now())
    t = local.timetz().replace(tzinfo=None)
    return DEFER_WINDOW_START <= t < DEFER_WINDOW_END


def process_after_for_deferred_submit(*, now: datetime | None = None) -> datetime:
    """Nejdřívější okamžik zpracování fronty — dnes 17:00 v lokální TZ."""
    local = timezone.localtime(now or timezone.now())
    day = local.date()
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(day, PROCESS_AFTER_TIME), tz)


def _local_day_start_end(day, tz):
    start = timezone.make_aware(datetime.combine(day, time.min), tz)
    return start, start + timedelta(days=1)


__all__ = [
    "DEFER_WINDOW_END",
    "DEFER_WINDOW_START",
    "PROCESS_AFTER_TIME",
    "is_deferred_svoz_matrix_window",
    "process_after_for_deferred_submit",
]
