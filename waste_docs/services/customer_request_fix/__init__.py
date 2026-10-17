"""Kompatibilní alias — kanonický balíček je customer_request_form."""

from waste_docs.services.customer_request_form.actions import (
    cancel_fix,
    hard_delete_fix,
    resubmit_fix,
    save_fix,
    status_after_resubmit,
)
from waste_docs.services.customer_request_form.permissions import (
    EDITABLE_STATUSES,
    can_delete_customer_request,
    can_fix_customer_request,
)
from waste_docs.services.customer_request_form.persist import apply_form_to_request

__all__ = [
    "EDITABLE_STATUSES",
    "apply_form_to_request",
    "can_delete_customer_request",
    "can_fix_customer_request",
    "cancel_fix",
    "hard_delete_fix",
    "resubmit_fix",
    "save_fix",
    "status_after_resubmit",
]
