"""Uložení synchronizovaného stavu a napojení na události."""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from customer_requests.models import CustomerRequest
from waste_docs.models import Pruvodka
from waste_docs.services.customer_request_audit import log_customer_request_action
from waste_docs.services.customer_request_status.align_ride_date import align_request_target_date_to_ride
from waste_docs.services.customer_request_status.resolve import resolve_operational_status
from waste_docs.services.customer_request_status.restore_auto_reschedule import (
    restore_auto_reschedule_if_false_positive,
)
from waste_docs.services.customer_request_status.ride_state import load_ride, ride_is_active

SYNC_AUDIT_ACTION = "status_sync_auto"


def _clear_invalid_ride_links(cr: CustomerRequest, *, new_status: str) -> list[str]:
    update_fields: list[str] = []
    if new_status == CustomerRequest.Status.CANCELLED:
        if cr.planned_pruvodka_id:
            cr.planned_pruvodka_id = None
            update_fields.append("planned_pruvodka")
        if cr.planned_follow_up_pruvodka_id:
            cr.planned_follow_up_pruvodka_id = None
            update_fields.append("planned_follow_up_pruvodka")
        return update_fields
    if new_status == CustomerRequest.Status.REQUIRES_RESCHEDULE:
        if cr.planned_pruvodka_id:
            cr.planned_pruvodka_id = None
            update_fields.append("planned_pruvodka")
        if cr.planned_follow_up_pruvodka_id:
            cr.planned_follow_up_pruvodka_id = None
            update_fields.append("planned_follow_up_pruvodka")
        return update_fields

    if new_status == CustomerRequest.Status.VISIBLE_FOR_DISPATCH:
        primary = load_ride(cr.planned_pruvodka_id)
        follow = load_ride(cr.planned_follow_up_pruvodka_id)
        if cr.planned_pruvodka_id and not ride_is_active(primary):
            cr.planned_pruvodka_id = None
            update_fields.append("planned_pruvodka")
        if cr.planned_follow_up_pruvodka_id and not ride_is_active(follow):
            cr.planned_follow_up_pruvodka_id = None
            update_fields.append("planned_follow_up_pruvodka")
    return update_fields


def sync_invoice_overdue_status(cr: CustomerRequest, *, today=None) -> bool:
    if not cr.requires_advance_invoice:
        return False
    if cr.status != CustomerRequest.Status.SUBMITTED:
        return False
    due = cr.invoice_due_date
    if not due:
        return False
    ref = today or timezone.localdate()
    if due >= ref:
        return False
    cr.status = CustomerRequest.Status.INVOICE_OVERDUE
    cr.save(update_fields=["status", "updated_at"])
    log_customer_request_action(
        cr,
        cr.created_by,
        "invoice_overdue_auto",
        "Automaticky označeno po splatnosti zálohy.",
    )
    return True


def sync_customer_request_status(
    cr: CustomerRequest,
    *,
    actor=None,
    reason: str = "",
    persist: bool = True,
) -> bool:
    sync_invoice_overdue_status(cr)
    if cr.status == CustomerRequest.Status.INVOICE_OVERDUE:
        return False

    restored = restore_auto_reschedule_if_false_positive(cr, actor=actor, persist=persist)
    aligned = align_request_target_date_to_ride(cr, actor=actor, persist=persist)

    new_status = resolve_operational_status(cr)
    if not new_status or new_status == cr.status:
        return restored or aligned

    note = (reason or "").strip() or f"{cr.status} → {new_status}"
    link_fields = _clear_invalid_ride_links(cr, new_status=new_status)
    cr.status = new_status
    update_fields = ["status", "updated_at", *link_fields]

    if not persist:
        return True

    cr.save(update_fields=update_fields)
    log_customer_request_action(cr, actor or cr.created_by, SYNC_AUDIT_ACTION, note)
    return True


def _requests_for_pruvodka(pruvodka: Pruvodka):
    pk = pruvodka.pk
    return CustomerRequest.objects.filter(
        Q(planned_pruvodka_id=pk) | Q(planned_follow_up_pruvodka_id=pk)
    )


def sync_for_pruvodka(pruvodka: Pruvodka, *, actor=None) -> int:
    updated = 0
    for cr in _requests_for_pruvodka(pruvodka):
        if sync_customer_request_status(
            cr,
            actor=actor,
            reason=f"Sync po jízdě #{pruvodka.pk}",
        ):
            updated += 1
    return updated


def sync_queryset(qs) -> int:
    updated = 0
    for cr in qs:
        if sync_customer_request_status(cr):
            updated += 1
    return updated


def sync_page_items(page_obj) -> int:
    return sync_queryset(page_obj.object_list)
