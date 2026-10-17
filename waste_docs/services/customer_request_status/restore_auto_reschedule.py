"""Náprava omylem nastaveného requires_reschedule po přeplánování jízdy dispečerem."""

from __future__ import annotations

import re

from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_audit import log_customer_request_action
from waste_docs.services.customer_request_status.align_ride_date import RIDE_RESCHEDULED_AUDIT_ACTION
from waste_docs.services.customer_request_status.ride_state import (
    load_ride,
    ride_is_active,
    rides_fulfill_request,
)

AUTO_SYNC_ACTION = "status_sync_auto"
DISPATCHER_RESCHEDULE_ACTION = "dispatcher_requires_reschedule"
_RIDE_PK_RE = re.compile(r"(?:Sync po jízdě|Jízda)\s*#(\d+)")


def _audit_rows(cr: CustomerRequest):
    return list(cr.audit_logs.all()[:80])


def _is_auto_requires_reschedule_latest(logs) -> bool:
    relevant = [
        row
        for row in logs
        if row.action in {AUTO_SYNC_ACTION, DISPATCHER_RESCHEDULE_ACTION}
    ]
    if not relevant:
        return False
    latest = relevant[0]
    if latest.action != AUTO_SYNC_ACTION:
        return False
    note = latest.note or ""
    return "→" in note and "requires_reschedule" in note.split("→")[-1]


def _ride_id_from_audit(logs) -> int | None:
    for row in logs:
        match = _RIDE_PK_RE.search(row.note or "")
        if match:
            return int(match.group(1))
    return None


def restore_auto_reschedule_if_false_positive(
    cr: CustomerRequest,
    *,
    actor=None,
    persist: bool = True,
) -> bool:
    """Vrátí požadavek z falešného Opravit, když dispečer jen posunul existující jízdu."""
    if cr.status != CustomerRequest.Status.REQUIRES_RESCHEDULE:
        return False

    logs = _audit_rows(cr)
    if not _is_auto_requires_reschedule_latest(logs):
        return False

    ride = load_ride(cr.planned_pruvodka_id)
    if not ride_is_active(ride):
        ride = load_ride(_ride_id_from_audit(logs))
    if not ride_is_active(ride):
        return False

    follow = load_ride(cr.planned_follow_up_pruvodka_id)
    new_status = (
        CustomerRequest.Status.DONE
        if rides_fulfill_request(cr, ride, follow)
        else CustomerRequest.Status.PLANNED
    )
    old_date = cr.target_date
    cr.planned_pruvodka = ride
    cr.target_date = ride.drive_date
    cr.status = new_status
    if not persist:
        return True

    cr.save(update_fields=["planned_pruvodka", "target_date", "status", "updated_at"])
    new_label = ride.drive_date.strftime("%d.%m.%Y") if ride.drive_date else "—"
    note = f"Jízda #{ride.pk} přeplánována na {new_label}"
    if old_date and old_date != ride.drive_date:
        note += f" (původní termín požadavku {old_date.strftime('%d.%m.%Y')})"
    log_customer_request_action(
        cr,
        actor or cr.created_by,
        RIDE_RESCHEDULED_AUDIT_ACTION,
        note,
    )
    return True
