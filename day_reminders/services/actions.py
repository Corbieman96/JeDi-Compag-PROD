from __future__ import annotations

from datetime import date

from django.db import models
from django.db import transaction
from django.utils import timezone

from day_reminders.models import DayReminder, DayReminderCompletion, DayReminderException
from day_reminders.card_colors import normalize_card_color
from day_reminders.note_group import normalize_note_group
from day_reminders.services.monthly_recurrence import normalize_monthly_rule


def normalize_repeat_weekdays(raw: list[int] | None) -> list[int]:
    """Unikátní seřazená čísla 0..6; prázdný vstup = []."""
    if not raw:
        return []
    out: set[int] = set()
    for x in raw:
        try:
            n = int(x)
            if 0 <= n <= 6:
                out.add(n)
        except (TypeError, ValueError):
            continue
    return sorted(out)


@transaction.atomic
def create_reminder(
    *,
    user,
    title: str,
    text: str,
    kind: str,
    pinned_date: date | None = None,
    repeat_weekdays: list[int] | None = None,
    repeat_monthly: dict | None = None,
    repeat_active_from: date | None = None,
    repeat_active_until: date | None = None,
    rolling_start: date | None = None,
    card_color: str | None = None,
    note_group: str | None = None,
) -> DayReminder:
    tl = (title or "").strip()
    if not tl:
        raise ValueError("Chybí název.")
    if kind not in {k.value for k in DayReminder.Kind}:
        raise ValueError("Neplatný typ.")

    obj = DayReminder(
        title=tl,
        text=(text or "").strip(),
        kind=kind,
        note_group=normalize_note_group(note_group),
        card_color=normalize_card_color(card_color),
        created_by=user if user.is_authenticated else None,
    )
    if kind == DayReminder.Kind.ONE_OFF:
        if pinned_date is None:
            raise ValueError("U jednorázové chybí datum.")
        obj.pinned_date = pinned_date
    elif kind == DayReminder.Kind.WEEKLY:
        days = normalize_repeat_weekdays(repeat_weekdays)
        if not days:
            raise ValueError("Vyberte alespoň jeden den v týdnu.")
        obj.repeat_weekdays = days
        obj.repeat_active_from = repeat_active_from
        obj.repeat_active_until = repeat_active_until
    elif kind == DayReminder.Kind.MONTHLY:
        rule = normalize_monthly_rule(repeat_monthly)
        obj.repeat_monthly = rule
        obj.repeat_active_from = repeat_active_from
        obj.repeat_active_until = repeat_active_until
    elif kind == DayReminder.Kind.ROLLING:
        if rolling_start is None:
            raise ValueError("Chybí datum začátku přenášení.")
        obj.rolling_start = rolling_start
    obj.save()
    return obj


@transaction.atomic
def toggle_reminder_completion_for_day(pk: int, day: date, user) -> bool:
    reminder = DayReminder.objects.filter(pk=pk).first()
    if not reminder:
        raise ValueError("Poznámka neexistuje.")
    completion = DayReminderCompletion.objects.filter(reminder_id=pk, resolved_on=day).first()
    if completion:
        completion.delete()
        if reminder.kind == DayReminder.Kind.ROLLING:
            reminder.completed_at = None
            reminder.save(update_fields=["completed_at", "updated_at"])
        return False
    DayReminderCompletion.objects.create(
        reminder=reminder,
        resolved_on=day,
        resolved_by=user if getattr(user, "is_authenticated", False) else None,
    )
    if reminder.kind == DayReminder.Kind.ROLLING:
        reminder.completed_at = timezone.now()
        reminder.save(update_fields=["completed_at", "updated_at"])
    return True


def snooze_reminder(pk: int, until: date | None) -> int:
    if until is None:
        raise ValueError("Chybí datum odložení.")
    return DayReminder.objects.filter(pk=pk).update(
        snoozed_until=until
    )


@transaction.atomic
def add_weekly_exception(reminder_pk: int, original_date: date, rescheduled_to: date) -> None:
    if original_date == rescheduled_to:
        raise ValueError("Cílové datum musí být jiné než původní.")
    r = DayReminder.objects.filter(
        pk=reminder_pk, kind__in=(DayReminder.Kind.WEEKLY, DayReminder.Kind.MONTHLY)
    ).first()
    if not r:
        raise ValueError("Poznámka neexistuje nebo není opakovaná.")
    DayReminderException.objects.update_or_create(
        reminder=r,
        original_date=original_date,
        defaults={"rescheduled_to": rescheduled_to},
    )


def update_reminder(
    pk: int,
    *,
    title: str,
    text: str,
    pinned_date: date | None = None,
    repeat_weekdays: list[int] | None = None,
    repeat_monthly: dict | None = None,
    repeat_active_from: date | None = None,
    repeat_active_until: date | None = None,
    rolling_start: date | None = None,
    card_color: str | None = None,
    note_group: str | None = None,
) -> DayReminder:
    r = DayReminder.objects.filter(pk=pk).first()
    if not r:
        raise ValueError("Poznámka neexistuje.")
    tl = (title or "").strip()
    if not tl:
        raise ValueError("Název nesmí být prázdný.")
    r.title = tl
    r.text = (text or "").strip()
    if note_group is not None:
        r.note_group = normalize_note_group(note_group)
    if card_color is not None:
        r.card_color = normalize_card_color(card_color)
    if r.kind == DayReminder.Kind.ONE_OFF:
        if pinned_date is None:
            raise ValueError("Chybí datum jednorázové poznámky.")
        r.pinned_date = pinned_date
    elif r.kind == DayReminder.Kind.WEEKLY:
        days = normalize_repeat_weekdays(repeat_weekdays)
        if not days:
            raise ValueError("Vyberte alespoň jeden den v týdnu.")
        r.repeat_weekdays = days
        r.repeat_active_from = repeat_active_from
        r.repeat_active_until = repeat_active_until
    elif r.kind == DayReminder.Kind.MONTHLY:
        rule = normalize_monthly_rule(repeat_monthly)
        r.repeat_monthly = rule
        r.repeat_active_from = repeat_active_from
        r.repeat_active_until = repeat_active_until
    elif r.kind == DayReminder.Kind.ROLLING:
        if rolling_start is None:
            raise ValueError("Chybí datum začátku přenášení.")
        r.rolling_start = rolling_start
    r.save()
    return r


@transaction.atomic
def delete_reminder(pk: int) -> int:
    n, _ = DayReminder.objects.filter(pk=pk).delete()
    return n


@transaction.atomic
def purge_completed(*, all_completed: bool = False, completed_before: date | None = None) -> int:
    """Trvale smaže dokončené DayReminder (ne jen odškrtnutí Completion)."""
    if all_completed:
        ids = set(DayReminderCompletion.objects.values_list("reminder_id", flat=True))
        ids.update(
            DayReminder.objects.filter(completed_at__isnull=False).values_list("pk", flat=True)
        )
        if not ids:
            return 0
        count = len(ids)
        DayReminder.objects.filter(pk__in=ids).delete()
        return count

    if completed_before is None:
        return 0

    old_ids = set(
        DayReminderCompletion.objects.filter(resolved_on__lt=completed_before).values_list(
            "reminder_id", flat=True
        )
    )
    keep_ids = set(
        DayReminderCompletion.objects.filter(resolved_on__gte=completed_before).values_list(
            "reminder_id", flat=True
        )
    )
    ids = old_ids - keep_ids
    # Rolling/legacy: hotové bez novější completion
    legacy_ids = set(
        DayReminder.objects.filter(completed_at__isnull=False)
        .exclude(pk__in=keep_ids)
        .values_list("pk", flat=True)
    )
    ids |= legacy_ids
    # Jednorázové na dny před cutoffem (i bez completion — vyčistí staré dny)
    one_off_old = set(
        DayReminder.objects.filter(
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date__lt=completed_before,
        ).values_list("pk", flat=True)
    )
    ids |= one_off_old
    if not ids:
        return 0
    count = len(ids)
    DayReminder.objects.filter(pk__in=ids).delete()
    return count


def purge_stale_weekly_ended() -> int:
    """Smaže denní vyřešení u týdenních připomínek po skončení platnosti."""
    n, _ = DayReminderCompletion.objects.filter(
        reminder__kind__in=(DayReminder.Kind.WEEKLY, DayReminder.Kind.MONTHLY),
        reminder__repeat_active_until__isnull=False,
        resolved_on__gt=models.F("reminder__repeat_active_until"),
    ).delete()
    return n
