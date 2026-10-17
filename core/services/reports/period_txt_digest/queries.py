"""Načtení dat pro TXT výcuc (jen čtení)."""

from __future__ import annotations

from datetime import date, timedelta

from customer_requests.models import CustomerRequest, CustomerRequestAuditLog
from day_reminders.models import DayReminder, DayReminderCompletion, DayReminderException
from day_reminders.services.queries import reminders_for_date
from waste_docs.models import Pruvodka

MAX_RANGE_DAYS = 92
MAX_ROWS_PER_SECTION = 10_000


def iter_days(date_from: date, date_to: date):
    d = date_from
    while d <= date_to:
        yield d
        d += timedelta(days=1)


def clamp_range(date_from: date, date_to: date) -> tuple[date, date, bool]:
    """Vrátí (from, to, truncated)."""
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    span = (date_to - date_from).days + 1
    if span <= MAX_RANGE_DAYS:
        return date_from, date_to, False
    return date_from, date_from + timedelta(days=MAX_RANGE_DAYS - 1), True


def fetch_rides(date_from: date, date_to: date) -> tuple[list[Pruvodka], bool]:
    qs = (
        Pruvodka.objects.filter(drive_date__gte=date_from, drive_date__lte=date_to)
        .select_related(
            "activity",
            "name",
            "ico",
            "address",
            "waste_type",
            "waste_code",
            "waste_category",
            "vehicle_rz",
            "driver",
            "suffix",
            "container_passport",
            "created_by",
            "follow_up_parent",
            "archived_by",
            "source_waste_suffix_pair",
        )
        .prefetch_related("attachments")
        .order_by("drive_date", "ride_group_number", "ride_sequence", "pk")
    )
    total = qs.count()
    truncated = total > MAX_ROWS_PER_SECTION
    return list(qs[:MAX_ROWS_PER_SECTION]), truncated


def fetch_requests(date_from: date, date_to: date) -> tuple[list[CustomerRequest], bool]:
    qs = (
        CustomerRequest.objects.filter(target_date__gte=date_from, target_date__lte=date_to)
        .select_related(
            "created_by",
            "name",
            "activity",
            "vehicle_kind",
            "waste_type",
            "suffix",
            "address",
            "follow_up_activity",
            "follow_up_parent_request",
            "recurrence_parent_request",
            "planned_pruvodka",
            "planned_follow_up_pruvodka",
            "invoice_confirmed_by",
            "dispatcher_review_by",
        )
        .prefetch_related("attachments", "audit_logs")
        .order_by("target_date", "pk")
    )
    total = qs.count()
    truncated = total > MAX_ROWS_PER_SECTION
    rows = list(qs[:MAX_ROWS_PER_SECTION])
    return rows, truncated


def fetch_notes_occurrences(date_from: date, date_to: date) -> tuple[list[tuple[date, DayReminder]], bool]:
    """Seznam (datum výskytu, reminder) v období."""
    out: list[tuple[date, DayReminder]] = []
    truncated = False
    for d in iter_days(date_from, date_to):
        for rem in reminders_for_date(d):
            out.append((d, rem))
            if len(out) >= MAX_ROWS_PER_SECTION:
                truncated = True
                return out, truncated
    return out, truncated


def load_note_side_data(reminder_ids: list[int], date_from: date, date_to: date):
    completions = list(
        DayReminderCompletion.objects.filter(
            reminder_id__in=reminder_ids,
            resolved_on__gte=date_from,
            resolved_on__lte=date_to,
        )
        .select_related("resolved_by")
        .order_by("resolved_on", "pk")
    )
    exceptions = list(
        DayReminderException.objects.filter(reminder_id__in=reminder_ids)
        .filter(
            models_q_original_or_target(date_from, date_to),
        )
        .order_by("original_date", "pk")
    )
    return completions, exceptions


def models_q_original_or_target(date_from: date, date_to: date):
    from django.db.models import Q

    return Q(original_date__gte=date_from, original_date__lte=date_to) | Q(
        rescheduled_to__gte=date_from, rescheduled_to__lte=date_to
    )


def audit_logs_for_requests(request_ids: list[int]) -> list[CustomerRequestAuditLog]:
    if not request_ids:
        return []
    return list(
        CustomerRequestAuditLog.objects.filter(request_id__in=request_ids)
        .select_related("actor")
        .order_by("created_at", "pk")
    )
