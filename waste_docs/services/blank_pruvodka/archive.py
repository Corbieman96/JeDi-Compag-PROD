"""Archivace nepoužitých bianko průvodek."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from waste_docs.models import Pruvodka

from .constants import DEFAULT_ARCHIVE_REASON, is_blank_pruvodka_ride


class BlankPruvodkaArchiveError(ValueError):
    pass


def is_unused_blank_pruvodka(ride: Pruvodka) -> bool:
    if ride.is_archived or not is_blank_pruvodka_ride(ride):
        return False
    if not ride.is_blank_pruvodka:
        return False
    if ride.vehicle_rz_id or ride.driver_id:
        return False
    from .constants import is_blank_pruvodka_activity

    return is_blank_pruvodka_activity(ride.activity_id)


def archive_blank_pruvodka(
    *,
    pruvodka: Pruvodka,
    user: AbstractBaseUser,
    reason: str = "",
) -> None:
    if not is_unused_blank_pruvodka(pruvodka):
        raise BlankPruvodkaArchiveError(
            "Archivovat lze jen nepoužitou bianko průvodku (bez řidiče a RZ, stále režim Bianko)."
        )
    reason_clean = (reason or DEFAULT_ARCHIVE_REASON).strip()[:200]
    pruvodka.is_archived = True
    pruvodka.archived_at = timezone.now()
    pruvodka.archived_by = user
    pruvodka.archive_reason = reason_clean
    pruvodka.save(update_fields=("is_archived", "archived_at", "archived_by", "archive_reason"))


def archive_unused_blank_for_day(
    *,
    drive_date: date,
    user: AbstractBaseUser,
    reason: str = "",
) -> int:
    qs = Pruvodka.objects.filter(
        drive_date=drive_date,
        is_archived=False,
        is_blank_pruvodka=True,
    )
    archived = 0
    with transaction.atomic():
        for ride in qs.select_for_update():
            if not is_unused_blank_pruvodka(ride):
                continue
            archive_blank_pruvodka(pruvodka=ride, user=user, reason=reason)
            archived += 1
    return archived
