from __future__ import annotations

from dataclasses import dataclass

from customer_requests.models import CustomerRequest

_AUDIT_FALLBACK_ACTIONS: dict[str, tuple[str, ...]] = {
    CustomerRequest.Status.RETURNED_FOR_FIX: ("dispatcher_returned",),
    CustomerRequest.Status.REQUIRES_RESCHEDULE: ("dispatcher_requires_reschedule",),
    CustomerRequest.Status.INVOICE_REJECTED: ("invoice_rejected",),
    CustomerRequest.Status.INVOICE_OVERDUE: (
        "invoice_unpaid_overdue",
        "invoice_overdue_auto",
    ),
    CustomerRequest.Status.CANCELLED: ("cancel", "dispatcher_cancelled"),
}

_FIELD_BY_STATUS: dict[str, str] = {
    CustomerRequest.Status.RETURNED_FOR_FIX: "dispatcher_note",
    CustomerRequest.Status.REQUIRES_RESCHEDULE: "dispatcher_note",
    CustomerRequest.Status.INVOICE_REJECTED: "invoice_note",
    CustomerRequest.Status.INVOICE_OVERDUE: "invoice_note",
    CustomerRequest.Status.CANCELLED: "dispatcher_note",
}

_LABEL_BY_STATUS: dict[str, str] = {
    CustomerRequest.Status.RETURNED_FOR_FIX: "Poznámka dispečera",
    CustomerRequest.Status.REQUIRES_RESCHEDULE: "Nutné přeplánovat",
    CustomerRequest.Status.INVOICE_REJECTED: "Důvod zamítnutí zálohy",
    CustomerRequest.Status.INVOICE_OVERDUE: "Poznámka k záloze",
    CustomerRequest.Status.CANCELLED: "Důvod zrušení",
}


@dataclass(frozen=True)
class SubmitterFixFeedback:
    label: str
    text: str


def _latest_audit_note(item: CustomerRequest, actions: tuple[str, ...]) -> str:
    log = (
        item.audit_logs.filter(action__in=actions)
        .exclude(note="")
        .order_by("-created_at", "-id")
        .first()
    )
    if log:
        return (log.note or "").strip()
    return ""


def build_submitter_fix_feedback(item: CustomerRequest) -> SubmitterFixFeedback | None:
    status = item.status
    if status not in _LABEL_BY_STATUS:
        return None

    text = ""
    field_name = _FIELD_BY_STATUS.get(status)
    if field_name:
        text = (getattr(item, field_name, None) or "").strip()
    if not text:
        text = _latest_audit_note(item, _AUDIT_FALLBACK_ACTIONS.get(status, ()))
    if not text:
        return None

    return SubmitterFixFeedback(label=_LABEL_BY_STATUS[status], text=text)
