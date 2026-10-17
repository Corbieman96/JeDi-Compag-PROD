from __future__ import annotations

from datetime import date

from django.db.models import Max, Q

from day_reminders.models import DayReminder, DayReminderCompletion, DayReminderException
from day_reminders.card_colors import attach_card_styles, card_color_choices, card_color_picker_options
from day_reminders.services.monthly_recurrence import monthly_matches_date


# (hodnota pro HTML select, český popis)
WEEKDAY_CHOICES = [
    (0, "Pondělí"),
    (1, "Úterý"),
    (2, "Středa"),
    (3, "Čtvrtek"),
    (4, "Pátek"),
    (5, "Sobota"),
    (6, "Neděle"),
]


def _snooze_allows(reminder: DayReminder, d: date) -> bool:
    if reminder.snoozed_until and d < reminder.snoozed_until:
        return False
    return True


def _repeat_range_ok(reminder: DayReminder, d: date) -> bool:
    if reminder.repeat_active_from and d < reminder.repeat_active_from:
        return False
    if reminder.repeat_active_until and d > reminder.repeat_active_until:
        return False
    return True


def _weekly_range_ok(reminder: DayReminder, d: date) -> bool:
    return _repeat_range_ok(reminder, d)


def _monthly_visible_on(reminder: DayReminder, d: date, by_original: dict, by_target: dict) -> bool:
    if not _repeat_range_ok(reminder, d):
        return False
    rid = reminder.pk
    if rid in by_target and d in by_target[rid]:
        return True
    if not monthly_matches_date(reminder.repeat_monthly, d):
        return False
    if rid in by_original and d in by_original[rid]:
        return False
    return True


def _weekly_visible_on(reminder: DayReminder, d: date, by_original: dict, by_target: dict) -> bool:
    """by_original / by_target: reminder_id -> dict date -> exception row"""
    if not _weekly_range_ok(reminder, d):
        return False
    rid = reminder.pk
    if rid in by_target and d in by_target[rid]:
        return True
    if d.weekday() not in reminder.weekly_weekday_set():
        return False
    if rid in by_original and d in by_original[rid]:
        return False
    return True


def _rolling_visible_on(reminder: DayReminder, d: date, resolved_on_by_reminder: dict[int, date]) -> bool:
    if reminder.rolling_start and d < reminder.rolling_start:
        return False
    resolved_on = resolved_on_by_reminder.get(reminder.pk)
    if resolved_on and d > resolved_on:
        return False
    return True


def _repeat_active_on_date(d: date):
    return (
        (Q(repeat_active_from__isnull=True) | Q(repeat_active_from__lte=d))
        & (Q(repeat_active_until__isnull=True) | Q(repeat_active_until__gte=d))
    )


def _not_snoozed_on_date(d: date):
    return Q(snoozed_until__isnull=True) | Q(snoozed_until__lte=d)


def _reminder_ids_with_exceptions_on(d: date) -> set[int]:
    return set(
        DayReminderException.objects.filter(Q(rescheduled_to=d) | Q(original_date=d)).values_list(
            "reminder_id", flat=True
        )
    )


def reminders_for_date(d: date) -> list[DayReminder]:
    """Připomínky zobrazené pro kalendářní den d."""
    out: list[DayReminder] = []

    one_off = list(
        DayReminder.objects.filter(
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=d,
        ).order_by("created_at")
    )
    for r in one_off:
        if _snooze_allows(r, d):
            out.append(r)

    rolling = list(
        DayReminder.objects.filter(
            kind=DayReminder.Kind.ROLLING,
            rolling_start__lte=d,
            completed_at__isnull=True,
        ).order_by("created_at")
    )
    rolling_ids = [r.pk for r in rolling]
    resolved_on_by_reminder: dict[int, date] = {}
    if rolling_ids:
        for row in (
            DayReminderCompletion.objects.filter(reminder_id__in=rolling_ids)
            .values("reminder_id")
            .annotate(latest=Max("resolved_on"))
        ):
            if row["latest"]:
                resolved_on_by_reminder[row["reminder_id"]] = row["latest"]
    for r in rolling:
        if not _snooze_allows(r, d):
            continue
        if not _rolling_visible_on(r, d, resolved_on_by_reminder):
            continue
        out.append(r)

    exception_reminder_ids = _reminder_ids_with_exceptions_on(d)

    weekly_qs = (
        DayReminder.objects.filter(kind=DayReminder.Kind.WEEKLY)
        .filter(
            Q(pk__in=exception_reminder_ids)
            | (_repeat_active_on_date(d) & _not_snoozed_on_date(d))
        )
        .prefetch_related("exceptions")
        .order_by("created_at")
    )
    by_original: dict[int, dict[date, object]] = {}
    by_target: dict[int, dict[date, object]] = {}
    weekly_list = list(weekly_qs)
    for r in weekly_list:
        by_original[r.pk] = {}
        by_target[r.pk] = {}
        for ex in r.exceptions.all():
            by_original[r.pk][ex.original_date] = ex
            by_target[r.pk][ex.rescheduled_to] = ex

    for r in weekly_list:
        if not _snooze_allows(r, d):
            continue
        if _weekly_visible_on(r, d, by_original, by_target):
            out.append(r)

    monthly_qs = (
        DayReminder.objects.filter(kind=DayReminder.Kind.MONTHLY)
        .filter(
            Q(pk__in=exception_reminder_ids)
            | (_repeat_active_on_date(d) & _not_snoozed_on_date(d))
        )
        .prefetch_related("exceptions")
        .order_by("created_at")
    )
    monthly_by_original: dict[int, dict[date, object]] = {}
    monthly_by_target: dict[int, dict[date, object]] = {}
    monthly_list = list(monthly_qs)
    for r in monthly_list:
        monthly_by_original[r.pk] = {}
        monthly_by_target[r.pk] = {}
        for ex in r.exceptions.all():
            monthly_by_original[r.pk][ex.original_date] = ex
            monthly_by_target[r.pk][ex.rescheduled_to] = ex

    for r in monthly_list:
        if not _snooze_allows(r, d):
            continue
        if _monthly_visible_on(r, d, monthly_by_original, monthly_by_target):
            out.append(r)

    resolved_ids = set(
        DayReminderCompletion.objects.filter(
            resolved_on=d,
            reminder_id__in=[r.pk for r in out],
        ).values_list("reminder_id", flat=True)
    )
    for r in out:
        r.is_resolved_for_selected_day = r.pk in resolved_ids
    attach_card_styles(out)
    return out


def build_dashboard_context(selected_date: date) -> dict:
    rows = reminders_for_date(selected_date)
    return {
        "day_reminders": rows,
        "day_reminders_count": len(rows),
        "day_reminders_weekday_choices": WEEKDAY_CHOICES,
        "day_reminder_card_color_choices": card_color_choices(),
        "day_reminder_card_color_options": card_color_picker_options(),
    }
