"""Založení navazujícího požadavku z primárního (druhý CustomerRequest)."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_audit import log_customer_request_action


def spawn_follow_up_customer_request(
    *,
    parent: CustomerRequest,
    actor: AbstractBaseUser,
) -> CustomerRequest:
    if not parent.has_follow_up or not parent.follow_up_activity_id:
        raise ValueError("Primární požadavek nemá navazující činnost.")
    if parent.follow_up_child_requests.exists():
        raise ValueError("Navazující požadavek už existuje.")

    follow_up_activity = parent.follow_up_activity
    assert follow_up_activity is not None

    child = CustomerRequest(
        created_by=parent.created_by,
        name=parent.name,
        activity=follow_up_activity,
        vehicle_kind=parent.vehicle_kind,
        waste_type=parent.waste_type,
        suffix=parent.suffix,
        address=parent.address,
        fulfillment_latitude=parent.fulfillment_latitude,
        fulfillment_longitude=parent.fulfillment_longitude,
        facility_address_snapshot=parent.facility_address_snapshot,
        contact_phone=parent.contact_phone,
        contact_note=parent.contact_note,
        target_date=parent.follow_up_target_date or parent.target_date,
        contract_number=parent.contract_number,
        note=parent.note,
        has_follow_up=False,
        follow_up_activity=None,
        follow_up_target_date=None,
        follow_up_parent_request=parent,
        is_recurring=False,
        recurrence_weekdays="",
        recurrence_until=None,
        requires_advance_invoice=False,
        advance_invoice_amount=None,
        invoice_due_date=None,
        status=parent.status,
    )
    child.save()
    log_customer_request_action(
        child,
        actor,
        "create",
        f"Navazující požadavek na požadavek #{parent.pk} ({follow_up_activity.name}).",
    )
    log_customer_request_action(
        parent,
        actor,
        "create",
        f"Požadavek založen. Navazující požadavek #{child.pk} ({follow_up_activity.name}).",
    )
    return child
