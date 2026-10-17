"""Srovnání termínu požadavku s datem navázané jízdy (přeplánování dispečerem)."""

from __future__ import annotations

from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_audit import log_customer_request_action
from waste_docs.services.customer_request_status.resolve import can_auto_sync_status
from waste_docs.services.customer_request_status.ride_state import (
    load_ride,
    ride_date_matches_request,
    ride_is_active,
)

RIDE_RESCHEDULED_AUDIT_ACTION = "ride_rescheduled_info"


def ride_rescheduled_banner_text(note: str | None) -> str:
    cleaned = (note or "").strip().rstrip(".")
    if cleaned:
        return f"Požadavek byl přeplánován dispečerem — {cleaned}."
    return "Požadavek byl přeplánován dispečerem."


def align_request_target_date_to_ride(
    cr: CustomerRequest,
    *,
    actor=None,
    persist: bool = True,
) -> bool:
    """Když dispečer posune jízdu, termín požadavku ji následuje. Stav se nemění na Opravit."""
    if not can_auto_sync_status(cr):
        return False
    primary = load_ride(cr.planned_pruvodka_id)
    if not ride_is_active(primary):
        return False
    if ride_date_matches_request(cr, primary):
        return False

    old = cr.target_date
    cr.target_date = primary.drive_date
    if not persist:
        return True

    cr.save(update_fields=["target_date", "updated_at"])
    new_label = primary.drive_date.strftime("%d.%m.%Y") if primary.drive_date else "—"
    note = f"Jízda #{primary.pk} přeplánována na {new_label}"
    if old and old != primary.drive_date:
        note += f" (původní termín požadavku {old.strftime('%d.%m.%Y')})"
    log_customer_request_action(
        cr,
        actor or cr.created_by,
        RIDE_RESCHEDULED_AUDIT_ACTION,
        note,
    )
    return True


def latest_ride_rescheduled_banner(cr: CustomerRequest) -> str | None:
    """Text infa pro zakladatele: dispečer přeplánoval jízdu, není to Opravit."""
    log = cr.audit_logs.filter(action=RIDE_RESCHEDULED_AUDIT_ACTION).first()
    if not log:
        return None
    return ride_rescheduled_banner_text(log.note)
