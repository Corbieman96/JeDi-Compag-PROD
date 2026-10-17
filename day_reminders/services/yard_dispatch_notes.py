"""Poznámky dispečera vzniklé po hlášení ze sběrného dvora (DayReminder.source_svoz_task)."""

from __future__ import annotations

from datetime import date

from day_reminders.models import DayReminder, DayReminderCompletion

def yard_dispatch_notes_for_date(d: date) -> list[DayReminder]:
    return list(
        DayReminder.objects.filter(
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=d,
            source_svoz_task__isnull=False,
        ).order_by("created_at")
    )


def yard_dispatch_notes_attention_for_date(d: date) -> tuple[bool, int]:
    """Vrátí (má_blikat, počet_nevyřešených) pro daný den na dashboardu."""
    notes = yard_dispatch_notes_for_date(d)
    if not notes:
        return False, 0
    resolved_ids = set(
        DayReminderCompletion.objects.filter(
            resolved_on=d,
            reminder_id__in=[n.pk for n in notes],
        ).values_list("reminder_id", flat=True)
    )
    unresolved = [n for n in notes if n.pk not in resolved_ids]
    return bool(unresolved), len(unresolved)
