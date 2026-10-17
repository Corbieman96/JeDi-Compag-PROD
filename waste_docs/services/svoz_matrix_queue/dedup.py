"""Deduplikace fronty matice — kontejner na cílový den."""

from __future__ import annotations

from waste_docs.models import SvozMatrixQueueEntry
from waste_docs.services.svoz_task_dedup import yard_container_already_fulfilled_on_target


def matrix_queue_line_already_scheduled(entry: SvozMatrixQueueEntry) -> bool:
    """True pokud už existuje jízda, OPEN nebo vyřízený úkol pro kontejner na cílový den."""
    return yard_container_already_fulfilled_on_target(
        subject_profile=entry.subject_profile,
        container_number=entry.container_numbers,
        target_date=entry.target_date,
    )


__all__ = [
    "matrix_queue_line_already_scheduled",
]
