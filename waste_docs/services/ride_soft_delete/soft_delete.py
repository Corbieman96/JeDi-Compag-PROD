from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from waste_docs.models import Pruvodka, PruvodkaSoftDeleteLog
from waste_docs.services.follow_up_chain import sync_parent_follow_up_open_state
from waste_docs.services.ride_soft_delete.errors import RideSoftDeleteError
from waste_docs.services.ride_soft_delete.validation import validate_soft_delete_reason


def _snapshot_fields(pruvodka: Pruvodka) -> dict:
    return {
        "snd_cislo_listu": (pruvodka.snd_cislo_listu or "").strip(),
        "drive_date": pruvodka.drive_date,
        "name_snapshot": (pruvodka.name_snapshot or "").strip(),
        "vehicle_rz_snapshot": (pruvodka.vehicle_rz_snapshot or "").strip(),
        "driver_snapshot": (pruvodka.driver_snapshot or "").strip(),
        "activity_snapshot": (pruvodka.activity_snapshot or "").strip(),
    }


def soft_delete_pruvodka(*, pruvodka: Pruvodka, actor, reason: str) -> PruvodkaSoftDeleteLog:
    """Soft smazání jízdy: archivace + auditní záznam. Neprovádí hard delete."""
    if pruvodka.is_archived:
        raise RideSoftDeleteError("Jízda je již smazána (archivována).")
    if pruvodka.follow_up_children.filter(is_archived=False).exists():
        raise RideSoftDeleteError(
            "Jízdu nelze smazat, protože na ni navazuje další aktivní jízda."
        )

    cleaned_reason = validate_soft_delete_reason(reason)
    snapshot = _snapshot_fields(pruvodka)
    parent = pruvodka.follow_up_parent
    now = timezone.now()

    with transaction.atomic():
        pruvodka.is_archived = True
        pruvodka.archived_at = now
        pruvodka.archived_by = actor
        pruvodka.archive_reason = cleaned_reason
        pruvodka.save(
            update_fields=("is_archived", "archived_at", "archived_by", "archive_reason")
        )
        log = PruvodkaSoftDeleteLog.objects.create(
            pruvodka=pruvodka,
            deleted_by=actor,
            reason=cleaned_reason,
            **snapshot,
        )

    if parent and not parent.is_archived:
        parent_loaded = (
            Pruvodka.objects.select_related("activity", "activity__follow_up_activity")
            .prefetch_related(
                "activity__follow_up_activities",
                "activity__follow_up_terminal_activities",
            )
            .filter(pk=parent.pk)
            .first()
        )
        if parent_loaded:
            sync_parent_follow_up_open_state(parent_loaded)

    from waste_docs.services.customer_request_status import sync_for_pruvodka

    sync_for_pruvodka(pruvodka, actor=actor)
    return log
