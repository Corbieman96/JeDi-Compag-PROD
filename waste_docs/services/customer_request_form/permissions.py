"""Oprávnění k opravě a smazání zákaznického požadavku zadavatelem."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from customer_requests.models import CustomerRequest
from users.constants import ROLE_ADMIN, ROLE_ZADAVATEL
from users.services.access import app_role

EDITABLE_STATUSES = frozenset(
    {
        CustomerRequest.Status.DRAFT,
        CustomerRequest.Status.RETURNED_FOR_FIX,
        CustomerRequest.Status.REQUIRES_RESCHEDULE,
        CustomerRequest.Status.INVOICE_REJECTED,
        CustomerRequest.Status.INVOICE_OVERDUE,
    }
)


def _is_owner_or_admin(user: AbstractBaseUser, item: CustomerRequest) -> bool:
    if user.is_superuser or app_role(user) == ROLE_ADMIN:
        return True
    return item.created_by_id == user.pk


def _can_submit(user: AbstractBaseUser) -> bool:
    r = app_role(user)
    return user.is_superuser or r in {ROLE_ZADAVATEL, ROLE_ADMIN}


def can_fix_customer_request(user: AbstractBaseUser, item: CustomerRequest) -> bool:
    if not _can_submit(user):
        return False
    if not _is_owner_or_admin(user, item):
        return False
    if item.status not in EDITABLE_STATUSES:
        return False
    if item.planned_pruvodka_id:
        return False
    return True


def can_delete_customer_request(user: AbstractBaseUser, item: CustomerRequest) -> bool:
    if not can_fix_customer_request(user, item):
        return False
    if item.planned_follow_up_pruvodka_id:
        return False
    return True
