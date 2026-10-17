"""Poznámka požadavku, která se propíše do jízdy (Pruvodka.contact_note)."""

from __future__ import annotations

from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_pair_note import pair_ride_note_for_customer_request


def ride_note_for_customer_request(cr: CustomerRequest) -> str:
    """Poznámka do jízdy: contact_note → pár → note."""
    contact = (cr.contact_note or "").strip()[:200]
    if contact:
        return contact
    pair_note = pair_ride_note_for_customer_request(cr)
    if pair_note:
        return pair_note
    return (cr.note or "").strip()[:200]


__all__ = ["ride_note_for_customer_request"]
