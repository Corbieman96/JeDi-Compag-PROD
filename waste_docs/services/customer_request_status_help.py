"""Vysvětlení stavů zákaznického požadavku pro seznam."""

from __future__ import annotations

from customer_requests.models import CustomerRequest

CUSTOMER_REQUEST_STATUS_HELP: dict[str, str] = {
    CustomerRequest.Status.DRAFT: "Požadavek je rozpracovaný a ještě nebyl odeslán ke schválení.",
    CustomerRequest.Status.SUBMITTED: "Požadavek čeká na schválení zálohové faktury kontrolorem.",
    CustomerRequest.Status.INVOICE_OVERDUE: "Zálohová faktura nebyla uhrazena ve splatnosti.",
    CustomerRequest.Status.INVOICE_REJECTED: "Kontrolor zálohovou fakturu zamítl.",
    CustomerRequest.Status.DISPATCHER_REVIEW: "Požadavek čeká na schválení dispečerem.",
    CustomerRequest.Status.RETURNED_FOR_FIX: "Dispečer vrátil požadavek zadavateli k opravě.",
    CustomerRequest.Status.REQUIRES_RESCHEDULE: "Požadavek vyžaduje přeplánování data (nebo jiné úpravy).",
    CustomerRequest.Status.VISIBLE_FOR_DISPATCH: "Požadavek je schválen — lze založit jízdu (řidič a RZ).",
    CustomerRequest.Status.PLANNED: "K požadavku už byla založena jízda.",
    CustomerRequest.Status.DONE: "Požadavek je dokončen.",
    CustomerRequest.Status.CANCELLED: "Požadavek byl zrušen.",
}


def customer_request_status_help_rows() -> list[dict[str, str]]:
    return [
        {
            "value": value,
            "label": label,
            "help": CUSTOMER_REQUEST_STATUS_HELP.get(value, ""),
        }
        for value, label in CustomerRequest.Status.choices
    ]
