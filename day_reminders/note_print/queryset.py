from __future__ import annotations

from datetime import date

from day_reminders.models import DayReminder
from day_reminders.note_print.scope import SCOPE_ALL, SCOPE_OTHER, SCOPE_REQUEST
from day_reminders.services.queries import reminders_for_date


def reminders_for_print(day: date, scope: str) -> list[DayReminder]:
    """Poznámky daného dne (stejná viditelnost jako dashboard), filtrované podle scope."""
    rows = reminders_for_date(day)
    if scope == SCOPE_REQUEST:
        return [r for r in rows if r.note_group == DayReminder.NoteGroup.REQUEST]
    if scope == SCOPE_OTHER:
        return [r for r in rows if r.note_group == DayReminder.NoteGroup.OTHER]
    if scope == SCOPE_ALL:
        return rows
    return rows
