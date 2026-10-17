"""Akce zadavatele při opravě požadavku."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from customer_requests.models import CustomerRequest
from waste_docs.forms.customer_request import CustomerRequestForm
from waste_docs.services.customer_request_audit import log_customer_request_action
from waste_docs.services.customer_request_form.persist import apply_form_to_request


def status_after_resubmit(item: CustomerRequest) -> str:
    if item.requires_advance_invoice:
        return CustomerRequest.Status.SUBMITTED
    return CustomerRequest.Status.DISPATCHER_REVIEW


def save_fix(*, form: CustomerRequestForm, item: CustomerRequest, actor: AbstractBaseUser) -> CustomerRequest:
    apply_form_to_request(form=form, item=item)
    log_customer_request_action(item, actor, "fix_saved", "Oprava uložena bez odeslání.")
    return item


def resubmit_fix(*, form: CustomerRequestForm, item: CustomerRequest, actor: AbstractBaseUser) -> CustomerRequest:
    apply_form_to_request(form=form, item=item)
    item.status = status_after_resubmit(item)
    item.save(update_fields=["status", "updated_at"])
    log_customer_request_action(item, actor, "resubmit", "Zadavatel poslal opravený požadavek znovu.")
    return item


def cancel_fix(*, item: CustomerRequest, actor: AbstractBaseUser, note: str = "") -> CustomerRequest:
    item.status = CustomerRequest.Status.CANCELLED
    item.save(update_fields=["status", "updated_at"])
    log_customer_request_action(item, actor, "cancel", note or "Zrušeno zadavatelem.")
    return item


def hard_delete_fix(*, item: CustomerRequest) -> None:
    for attachment in list(item.attachments.all()):
        attachment.file.delete(save=False)
        attachment.delete()
    item.delete()
