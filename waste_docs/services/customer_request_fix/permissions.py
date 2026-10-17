"""Kompatibilní re-export z customer_request_form."""

from waste_docs.services.customer_request_form.permissions import (
    EDITABLE_STATUSES,
    can_delete_customer_request,
    can_fix_customer_request,
)

__all__ = [
    "EDITABLE_STATUSES",
    "can_delete_customer_request",
    "can_fix_customer_request",
]
