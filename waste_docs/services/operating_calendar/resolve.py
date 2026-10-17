"""Provozní dny: víkendy z nastavení a ručně zadané svátky."""

from __future__ import annotations

from datetime import date, timedelta

from customer_requests.models import NoServiceCalendarDay


def _weekend_flags() -> tuple[bool, bool]:
    from core.models import AppSettings

    try:
        settings = AppSettings.load()
    except Exception:
        return True, True
    return bool(settings.no_service_on_saturday), bool(settings.no_service_on_sunday)


def _holiday_row(day: date) -> NoServiceCalendarDay | None:
    return NoServiceCalendarDay.objects.filter(closed_date=day).first()


def is_operating_day(day: date | None) -> bool:
    if not day:
        return False
    skip_sat, skip_sun = _weekend_flags()
    if skip_sat and day.weekday() == 5:
        return False
    if skip_sun and day.weekday() == 6:
        return False
    return _holiday_row(day) is None


def resolve_operating_date(day: date | None, *, max_hops: int = 31) -> date | None:
    """Vrátí den, kdy se jezdí. Neprovozní den posune na redirect nebo +1 den."""
    if not day:
        return None
    seen: set[date] = set()
    current = day
    for _ in range(max_hops):
        if current in seen:
            break
        seen.add(current)
        if is_operating_day(current):
            return current
        row = _holiday_row(current)
        if row and row.redirect_date and row.redirect_date != current:
            current = row.redirect_date
        else:
            current = current + timedelta(days=1)
    return current


def apply_operating_date_shift(day: date | None, *, user=None) -> tuple[date | None, str | None]:
    """Posune termín, pokud není provozní. Admin může nechat původní datum."""
    from waste_docs.services.customer_request_date_closure import can_bypass_date_closure

    if not day or can_bypass_date_closure(user):
        return day, None
    resolved = resolve_operating_date(day)
    if not resolved or resolved == day:
        return day, None
    note = (
        f"Termín {day.strftime('%d.%m.%Y')} je den bez svozu — "
        f"uloží se na {resolved.strftime('%d.%m.%Y')}."
    )
    return resolved, note
