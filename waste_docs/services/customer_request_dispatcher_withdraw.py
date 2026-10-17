"""Stažení schválení požadavku z dispatch fronty (dispečer omylem schválil)."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_audit import log_customer_request_action
from waste_docs.services.customer_request_form.cancel_reason import normalize_cancel_reason

ALLOWED_WITHDRAW_ACTIONS = frozenset({"return", "cancel"})


class DispatcherWithdrawError(Exception):
    pass


def can_withdraw_from_dispatch(item: CustomerRequest) -> bool:
    return (
        item.status == CustomerRequest.Status.VISIBLE_FOR_DISPATCH
        and not item.planned_pruvodka_id
    )


def withdraw_from_dispatch(
    *,
    item: CustomerRequest,
    actor: AbstractBaseUser,
    action: str,
    note: str = "",
) -> CustomerRequest:
    action = (action or "").strip()
    if action not in ALLOWED_WITHDRAW_ACTIONS:
        raise DispatcherWithdrawError("Neplatná akce.")

    if item.status != CustomerRequest.Status.VISIBLE_FOR_DISPATCH:
        raise DispatcherWithdrawError("Požadavek není ve frontě dispečera.")

    if item.planned_pruvodka_id:
        raise DispatcherWithdrawError("K požadavku už je založena jízda — schválení nelze vzít zpět.")

    note = (note or "").strip()
    if action == "cancel":
        try:
            note = normalize_cancel_reason(note)
        except ValueError as exc:
            raise DispatcherWithdrawError(str(exc)) from exc

    item.dispatcher_review_by = actor
    item.dispatcher_reviewed_at = timezone.now()
    item.dispatcher_note = note

    if action == "return":
        item.status = CustomerRequest.Status.RETURNED_FOR_FIX
        log_customer_request_action(item, actor, "dispatcher_returned", note or "Schválení staženo — vráceno k opravě.")
    else:
        item.status = CustomerRequest.Status.CANCELLED
        log_customer_request_action(item, actor, "dispatcher_cancelled", note)

    item.save(
        update_fields=[
            "status",
            "dispatcher_review_by",
            "dispatcher_reviewed_at",
            "dispatcher_note",
            "updated_at",
        ]
    )
    return item


__all__ = [
    "ALLOWED_WITHDRAW_ACTIONS",
    "DispatcherWithdrawError",
    "can_withdraw_from_dispatch",
    "withdraw_from_dispatch",
]
