"""Správa chybového logu (mazání řádků, označení jako přečtené)."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from waste_docs.models.yard_svoz_submit_error_log import YardSvozSubmitErrorLog

from .reclaim_space import reclaim_sqlite_space_after_delete
from .record import SOURCE_AUDIT_ONLY


def delete_row(*, pk: int) -> bool:
    deleted, _ = YardSvozSubmitErrorLog.objects.filter(pk=pk).delete()
    if deleted:
        reclaim_sqlite_space_after_delete()
    return deleted > 0


def delete_rows_for_subject(*, subject_profile_id: int) -> int:
    deleted, _ = (
        YardSvozSubmitErrorLog.objects.filter(subject_profile_id=subject_profile_id)
        .exclude(source__in=SOURCE_AUDIT_ONLY)
        .delete()
    )
    if deleted:
        reclaim_sqlite_space_after_delete()
    return int(deleted)


def acknowledge_unread(*, user: AbstractBaseUser) -> int:
    stamp = timezone.now()
    return YardSvozSubmitErrorLog.objects.filter(acknowledged_at__isnull=True).update(
        acknowledged_at=stamp,
        acknowledged_by=user,
    )


def acknowledge_unread_for_subject(
    *,
    subject_profile_id: int,
    user: AbstractBaseUser,
    day: date | None = None,
) -> int:
    """Po úspěšném svozu — schová dispečerský alert u tohoto dvora pro daný den."""
    target_day = day or timezone.localdate()
    stamp = timezone.now()
    return YardSvozSubmitErrorLog.objects.filter(
        subject_profile_id=subject_profile_id,
        submission_day=target_day,
        acknowledged_at__isnull=True,
    ).update(
        acknowledged_at=stamp,
        acknowledged_by=user,
    )
