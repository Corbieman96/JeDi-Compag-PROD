"""Jednorázové odeslání matice svozů z dvora na kalendářní den (v lokální TZ aplikace)."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.db.models import Exists, OuterRef
from django.utils import timezone

from waste_docs.models import SvozMatrixQueueEntry, SvozTask, YardHazardousWasteRequest


def _local_day_start_end(day):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), tz)
    end = start + timedelta(days=1)
    return start, end


def _yard_daily_submit_limit_disabled() -> bool:
    from core.models import AppSettings

    try:
        return bool(AppSettings.load().svoz_disable_yard_daily_submit_limit)
    except Exception:
        return False


def is_svoz_yard_daily_submit_limit_disabled() -> bool:
    """Globálně v adminu nastavenitelné přerušení denního limitu odeslání matice dvorem (viz AppSettings)."""
    return _yard_daily_submit_limit_disabled()


def svoz_subject_has_submitted_today(*, subject_profile_id: int, now=None) -> bool:
    """
    True, pokud už dnes vznikl alespoň jeden požadavek ze sběrného dvora
    (SvozTask, fronta matice nebo nebezpečný odpad) v aktuální kalendářní den lokálně.
    """
    if _yard_daily_submit_limit_disabled():
        return False
    day = timezone.localdate(now)
    start, end = _local_day_start_end(day)
    if SvozMatrixQueueEntry.objects.filter(
        subject_profile_id=subject_profile_id,
        submitted_at__gte=start,
        submitted_at__lt=end,
    ).exists():
        return True
    if SvozTask.objects.filter(
        subject_profile_id=subject_profile_id,
        created_at__gte=start,
        created_at__lt=end,
    ).exists():
        return True
    return YardHazardousWasteRequest.objects.filter(
        subject_profile_id=subject_profile_id,
        created_at__gte=start,
        created_at__lt=end,
    ).exists()


def svoz_subjects_with_svoz_submission_today(subject_profile_ids: list[int], *, now=None) -> frozenset[int]:
    """Pro dané subjekty vrátí ty, které už dnes poslaly aspoň jednu šarži (bulk GET)."""
    if _yard_daily_submit_limit_disabled():
        return frozenset()
    if not subject_profile_ids:
        return frozenset()
    day = timezone.localdate(now)
    start, end = _local_day_start_end(day)
    qs_queue = SvozMatrixQueueEntry.objects.filter(
        subject_profile_id__in=subject_profile_ids,
        submitted_at__gte=start,
        submitted_at__lt=end,
    ).values_list("subject_profile_id", flat=True)
    qs_svoz = SvozTask.objects.filter(
        subject_profile_id__in=subject_profile_ids,
        created_at__gte=start,
        created_at__lt=end,
    ).values_list("subject_profile_id", flat=True)
    qs_hazard = YardHazardousWasteRequest.objects.filter(
        subject_profile_id__in=subject_profile_ids,
        created_at__gte=start,
        created_at__lt=end,
    ).values_list("subject_profile_id", flat=True)
    return frozenset(list(qs_queue) + list(qs_svoz) + list(qs_hazard))


def svoz_today_any_exists_subquery():
    """Pro annotate na queryset NameSubjectProfile (OuterRef pk)."""
    if _yard_daily_submit_limit_disabled():
        return Exists(SvozTask.objects.filter(pk=-1))
    day = timezone.localdate()
    start, end = _local_day_start_end(day)
    return Exists(
        SvozMatrixQueueEntry.objects.filter(
            subject_profile_id=OuterRef("pk"),
            submitted_at__gte=start,
            submitted_at__lt=end,
        )
    ) | Exists(
        SvozTask.objects.filter(
            subject_profile_id=OuterRef("pk"),
            created_at__gte=start,
            created_at__lt=end,
        )
    ) | Exists(
        YardHazardousWasteRequest.objects.filter(
            subject_profile_id=OuterRef("pk"),
            created_at__gte=start,
            created_at__lt=end,
        )
    )


__all__ = [
    "is_svoz_yard_daily_submit_limit_disabled",
    "svoz_subject_has_submitted_today",
    "svoz_subjects_with_svoz_submission_today",
    "svoz_today_any_exists_subquery",
]
