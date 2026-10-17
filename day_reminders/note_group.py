from __future__ import annotations

from day_reminders.models import DayReminder


def normalize_note_group(raw: str | None) -> str:
    value = (raw or "").strip()
    allowed = {c.value for c in DayReminder.NoteGroup}
    if value in allowed:
        return value
    return DayReminder.NoteGroup.REQUEST
