"""Dopočet operativního stavu požadavku z reality jízd."""

from __future__ import annotations

from customer_requests.models import CustomerRequest

from waste_docs.services.customer_request_status.ride_state import (
    load_ride,
    ride_is_active,
    rides_fulfill_request,
)

WORKFLOW_LOCKED_STATUSES = frozenset(
    {
        CustomerRequest.Status.DRAFT,
        CustomerRequest.Status.SUBMITTED,
        CustomerRequest.Status.INVOICE_OVERDUE,
        CustomerRequest.Status.INVOICE_REJECTED,
        CustomerRequest.Status.DISPATCHER_REVIEW,
        CustomerRequest.Status.RETURNED_FOR_FIX,
        CustomerRequest.Status.REQUIRES_RESCHEDULE,
        CustomerRequest.Status.CANCELLED,
    }
)

OPERATIONAL_STATUSES = frozenset(
    {
        CustomerRequest.Status.VISIBLE_FOR_DISPATCH,
        CustomerRequest.Status.PLANNED,
        CustomerRequest.Status.DONE,
    }
)


def can_auto_sync_status(cr: CustomerRequest) -> bool:
    if cr.status in WORKFLOW_LOCKED_STATUSES:
        return False
    if cr.status in OPERATIONAL_STATUSES:
        return True
    if cr.dispatcher_reviewed_at:
        return True
    if cr.planned_pruvodka_id or cr.planned_follow_up_pruvodka_id:
        return True
    return False


def _visible_after_ride_loss(cr: CustomerRequest) -> str:
    if cr.dispatcher_reviewed_at:
        return CustomerRequest.Status.CANCELLED
    return CustomerRequest.Status.REQUIRES_RESCHEDULE


def resolve_operational_status(cr: CustomerRequest) -> str | None:
    if not can_auto_sync_status(cr):
        return None

    primary = load_ride(cr.planned_pruvodka_id)
    follow = load_ride(cr.planned_follow_up_pruvodka_id)

    if cr.planned_pruvodka_id and not ride_is_active(primary):
        return _visible_after_ride_loss(cr)

    if cr.planned_follow_up_pruvodka_id and not ride_is_active(follow):
        return CustomerRequest.Status.REQUIRES_RESCHEDULE

    if rides_fulfill_request(cr, primary, follow):
        return CustomerRequest.Status.DONE

    if ride_is_active(primary):
        return CustomerRequest.Status.PLANNED

    if cr.dispatcher_reviewed_at and cr.status not in {
        CustomerRequest.Status.REQUIRES_RESCHEDULE,
        CustomerRequest.Status.RETURNED_FOR_FIX,
    }:
        return CustomerRequest.Status.VISIBLE_FOR_DISPATCH

    return None
