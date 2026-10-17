"""Plánování data zobrazení požadavků ze sběrného dvora na dashboardu."""

from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone


def next_svoz_target_date(from_date=None):
    """
    Následující provozní den od from_date (výchozí dnes).
    Přeskočí sobotu/neděli a svátky podle Nastavení — Dny bez svozu.
    """
    from waste_docs.services.operating_calendar.resolve import resolve_operating_date

    base = from_date or timezone.localdate()
    return resolve_operating_date(base + timedelta(days=1))


def svoz_target_date_for_matrix_submit(*, now=None) -> date:
    """Cílový den úkolu svozu při odeslání matice SD — následující provozní den."""
    submission_day = timezone.localdate(now)
    return next_svoz_target_date(submission_day)


__all__ = ["next_svoz_target_date", "svoz_target_date_for_matrix_submit"]
