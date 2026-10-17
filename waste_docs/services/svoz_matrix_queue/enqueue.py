"""Zápis řádků matice do fronty (odložené zpracování)."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from catalogs.models import NameSubjectProfile
from waste_docs.models import SvozMatrixQueueEntry
from waste_docs.services.svoz_matrix_post_collect import SvozPendingLine
from waste_docs.services.svoz_matrix_queue.window import process_after_for_deferred_submit


def enqueue_svoz_matrix_lines(
    pending_lines: list[SvozPendingLine],
    subject: NameSubjectProfile,
    user: AbstractBaseUser,
    target_date: date,
    *,
    now=None,
) -> int:
    """
    Uloží řádky matice do DB fronty. Vrací počet vytvořených záznamů.
    Volat uvnitř transaction.atomic() volajícího, pokud je potřeba zámek subjektu.
    """
    if not pending_lines:
        return 0

    process_after = process_after_for_deferred_submit(now=now)
    submitted_at = now or timezone.now()
    entries = [
        SvozMatrixQueueEntry(
            subject_profile=subject,
            created_by=user,
            source_waste_suffix_pair=pline.pair,
            container_numbers=pline.container_numbers,
            matrix_display_label=pline.matrix_display_label,
            yard_contact_note=pline.yard_contact_note,
            target_date=target_date,
            submitted_at=submitted_at,
            process_after=process_after,
            status=SvozMatrixQueueEntry.Status.PENDING,
        )
        for pline in pending_lines
    ]
    with transaction.atomic():
        for entry in entries:
            entry.save()
    return len(entries)


__all__ = ["enqueue_svoz_matrix_lines"]
