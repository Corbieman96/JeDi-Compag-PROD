"""Kompatibilní re-export z customer_request_form."""

from waste_docs.services.customer_request_form.persist import (
    apply_form_to_request,
    save_attachments_from_form,
)

__all__ = [
    "apply_form_to_request",
    "save_attachments_from_form",
]
