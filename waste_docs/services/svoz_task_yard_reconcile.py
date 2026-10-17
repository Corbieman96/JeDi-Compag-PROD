"""Uzavření OPEN SvozTask po jízdě a dokončení poznámek ze sběrného dvora."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser

from catalogs.models import NameSubjectProfile
from day_reminders.models import DayReminder, DayReminderCompletion
from waste_docs.models import Pruvodka, SvozTask
from waste_docs.services.container_passport_ride_validation import normalize_container_number
from waste_docs.services.svoz_task_dedup import dates_for_yard_submit


def fulfillment_dates_for_svoz_task(task: SvozTask) -> list[date]:
    return dates_for_yard_submit(target_date=task.target_date, now=task.created_at)


def _container_numbers_from_pruvodka(pruvodka: Pruvodka) -> list[str]:
    numbers: list[str] = []
    for raw in (pruvodka.container_number, pruvodka.container_number_2):
        num = normalize_container_number(raw or "")
        if num and num not in numbers:
            numbers.append(num)
    return numbers


def _subject_profile_id_for_pruvodka(pruvodka: Pruvodka) -> int | None:
    return (
        NameSubjectProfile.objects.filter(
            name_id=pruvodka.name_id,
            yard_settings__is_collection_yard=True,
        )
        .values_list("pk", flat=True)
        .first()
    )


def find_open_svoz_tasks_for_yard_container(
    *,
    subject_profile_id: int,
    container_number: str,
    dates: list[date],
) -> list[SvozTask]:
    number = normalize_container_number(container_number)
    if not number or not dates:
        return []
    seen_days: set[date] = set()
    target_dates: list[date] = []
    for day in dates:
        if day in seen_days:
            continue
        seen_days.add(day)
        target_dates.append(day)
    return list(
        SvozTask.objects.filter(
            subject_profile_id=subject_profile_id,
            status=SvozTask.Status.OPEN,
            resolved_pruvodka__isnull=True,
            target_date__in=target_dates,
            container_numbers__iexact=number,
        ).order_by("created_at", "pk")
    )


def complete_yard_dispatch_notes_for_svoz_task(task: SvozTask) -> int:
    count = 0
    for reminder in DayReminder.objects.filter(source_svoz_task_id=task.pk):
        resolved_on = reminder.pinned_date or task.target_date
        if not resolved_on:
            continue
        _, created = DayReminderCompletion.objects.get_or_create(
            reminder_id=reminder.pk,
            resolved_on=resolved_on,
        )
        if created:
            count += 1
    return count


def _close_svoz_task(task: SvozTask, pruvodka: Pruvodka) -> None:
    task.status = SvozTask.Status.DONE
    task.resolved_pruvodka = pruvodka
    task.save(update_fields=["status", "resolved_pruvodka_id"])
    complete_yard_dispatch_notes_for_svoz_task(task)


def reconcile_open_svoz_tasks_for_yard_ride(pruvodka: Pruvodka) -> int:
    """Hromadné uzavírání OPEN úkolů podle jízdy zrušeno — propojení jen přes auto-průvodku."""
    return 0


def reconcile_open_svoz_task_if_fulfilled(task: SvozTask) -> bool:
    """Existující jízda jiného úkolu už neuzavírá OPEN požadavek (Bakov OK)."""
    return False


def retry_auto_pruvodka_for_open_task(
    task: SvozTask,
    actor: AbstractBaseUser | None = None,
) -> tuple[bool, str | None]:
    """Znovu zkusí auto-průvodku u OPEN úkolu s přiřazeným řidičem."""
    from waste_docs.services.svoz_task_auto_pruvodka import try_create_pruvodka_for_assigned_svoz_task

    if task.status != SvozTask.Status.OPEN or not task.assigned_driver_id:
        return False, None
    who = actor or task.created_by
    if not who:
        return False, None
    return try_create_pruvodka_for_assigned_svoz_task(task, who)


__all__ = [
    "complete_yard_dispatch_notes_for_svoz_task",
    "find_open_svoz_tasks_for_yard_container",
    "fulfillment_dates_for_svoz_task",
    "reconcile_open_svoz_task_if_fulfilled",
    "reconcile_open_svoz_tasks_for_yard_ride",
    "retry_auto_pruvodka_for_open_task",
]
