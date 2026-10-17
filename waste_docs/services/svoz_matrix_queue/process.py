"""Zpracování fronty matice — deduplikace a vytvoření SvozTask po 17:00."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from waste_docs.models import SvozMatrixQueueEntry
from waste_docs.services.svoz_dispatch.yard_day_reminder import (
    create_day_reminder_for_svoz_task,
    should_create_yard_dispatch_note,
)
from waste_docs.services.svoz_matrix_post_collect import SvozPendingLine
from waste_docs.services.svoz_matrix_queue.dedup import matrix_queue_line_already_scheduled
from waste_docs.services.svoz_task_submit import submit_svoz_line_if_allowed


@dataclass
class SvozMatrixQueueProcessStats:
    processed: int = 0
    skipped_duplicate: int = 0
    failed: int = 0
    entry_ids: list[int] = field(default_factory=list)


def _pending_line_from_entry(entry: SvozMatrixQueueEntry) -> SvozPendingLine:
    pair = entry.source_waste_suffix_pair
    return SvozPendingLine(
        pair=pair,
        matrix_display_label=entry.matrix_display_label,
        yard_contact_note=entry.yard_contact_note,
        container_numbers=entry.container_numbers,
    )


def _process_one_entry(entry: SvozMatrixQueueEntry, *, now: datetime) -> str:
    """Vrátí výsledný status řetězec (processed / skipped_duplicate / failed)."""
    pline = _pending_line_from_entry(entry)
    subject = entry.subject_profile
    user = entry.created_by
    target = entry.target_date

    if matrix_queue_line_already_scheduled(entry):
        entry.last_error = "duplicate_open_task"
        return SvozMatrixQueueEntry.Status.SKIPPED_DUPLICATE

    result = submit_svoz_line_if_allowed(pline, subject, user, target)
    if result.skipped_duplicate:
        return SvozMatrixQueueEntry.Status.SKIPPED_DUPLICATE
    if not result.created or result.task is None:
        return SvozMatrixQueueEntry.Status.FAILED

    task = result.task
    pair = pline.pair
    if should_create_yard_dispatch_note(pair):
        create_day_reminder_for_svoz_task(task=task, pair=pair, created_by=user)

    entry.result_svoz_task = task
    return SvozMatrixQueueEntry.Status.PROCESSED


def process_due_svoz_matrix_queue(
    *,
    now: datetime | None = None,
    limit: int = 500,
) -> SvozMatrixQueueProcessStats:
    """
    Zpracuje záznamy fronty se statusem pending a process_after <= now.
    Idempotentní — již zpracované záznamy se neberou znovu.
    """
    now = now or timezone.now()
    stats = SvozMatrixQueueProcessStats()

    due_ids = list(
        SvozMatrixQueueEntry.objects.filter(
            status=SvozMatrixQueueEntry.Status.PENDING,
            process_after__lte=now,
        )
        .order_by("submitted_at", "pk")
        .values_list("pk", flat=True)[:limit]
    )

    for entry_id in due_ids:
        with transaction.atomic():
            entry = (
                SvozMatrixQueueEntry.objects.select_for_update()
                .select_related(
                    "subject_profile",
                    "created_by",
                    "source_waste_suffix_pair",
                    "source_waste_suffix_pair__yard_vehicle_kind",
                )
                .prefetch_related("source_waste_suffix_pair__yard_vehicle_kinds")
                .filter(pk=entry_id)
                .first()
            )
            if not entry or entry.status != SvozMatrixQueueEntry.Status.PENDING:
                continue
            if entry.process_after > now:
                continue

            entry.attempt_count += 1
            try:
                new_status = _process_one_entry(entry, now=now)
                entry.status = new_status
                entry.processed_at = now
                if new_status == SvozMatrixQueueEntry.Status.FAILED:
                    if not entry.last_error:
                        entry.last_error = "submit_svoz_line_if_allowed nevrátil úkol."
                elif new_status == SvozMatrixQueueEntry.Status.PROCESSED:
                    entry.last_error = ""
            except Exception as exc:  # noqa: BLE001 — fronta musí pokračovat dalšími záznamy
                entry.status = SvozMatrixQueueEntry.Status.FAILED
                entry.processed_at = now
                entry.last_error = str(exc)[:2000]
                stats.failed += 1
                entry.save(
                    update_fields=[
                        "status",
                        "processed_at",
                        "attempt_count",
                        "last_error",
                        "result_svoz_task_id",
                    ]
                )
                stats.entry_ids.append(entry_id)
                continue

            entry.save(
                update_fields=[
                    "status",
                    "processed_at",
                    "attempt_count",
                    "last_error",
                    "result_svoz_task_id",
                ]
            )
            stats.entry_ids.append(entry_id)
            if entry.status == SvozMatrixQueueEntry.Status.PROCESSED:
                stats.processed += 1
            elif entry.status == SvozMatrixQueueEntry.Status.SKIPPED_DUPLICATE:
                stats.skipped_duplicate += 1
            else:
                stats.failed += 1

    return stats


__all__ = ["SvozMatrixQueueProcessStats", "process_due_svoz_matrix_queue"]
