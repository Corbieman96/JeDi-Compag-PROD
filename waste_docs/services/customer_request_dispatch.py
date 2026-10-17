"""Fronta CustomerRequest pro dispatch a propojení s novou jízdou."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import QuerySet

from customer_requests.models import CustomerRequest
from users.constants import ROLE_ADMIN, ROLE_DISPECER
from users.services.access import app_role
from waste_docs.models import Pruvodka
from waste_docs.services.customer_request_audit import log_customer_request_action
from waste_docs.services.pruvodka_attachments import copy_customer_request_attachments_to_pruvodka


class CustomerRequestLinkError(Exception):
    pass


def can_view_customer_requests_dispatch(user: AbstractBaseUser) -> bool:
    if user.is_superuser:
        return True
    return app_role(user) in {ROLE_DISPECER, ROLE_ADMIN}


def customer_requests_visible_for_dispatch(
    user: AbstractBaseUser,
    day: date,
    *,
    limit: int = 80,
) -> QuerySet[CustomerRequest]:
    if not can_view_customer_requests_dispatch(user):
        return CustomerRequest.objects.none()
    return (
        CustomerRequest.objects.filter(
            status=CustomerRequest.Status.VISIBLE_FOR_DISPATCH,
            target_date=day,
            planned_pruvodka__isnull=True,
        )
        .select_related("name", "activity", "vehicle_kind", "created_by", "address", "waste_type", "suffix")
        .prefetch_related("activity__vehicle_kinds")
        .order_by("created_at")[:limit]
    )


def link_customer_request_to_pruvodka(
    cr: CustomerRequest,
    pruvodka: Pruvodka,
    *,
    actor,
) -> None:
    if cr.planned_pruvodka_id:
        raise CustomerRequestLinkError("K požadavku už je jízda založena.")
    if cr.status != CustomerRequest.Status.VISIBLE_FOR_DISPATCH:
        raise CustomerRequestLinkError("Požadavek není připraven pro plánování jízd.")

    if cr.has_follow_up and not cr.follow_up_child_requests.exists():
        pruvodka.follow_up_open = True
        pruvodka.save(update_fields=["follow_up_open"])

    copy_customer_request_attachments_to_pruvodka(cr, pruvodka)

    update_fields = ["planned_pruvodka", "status", "updated_at"]
    note = f"Jízda #{pruvodka.pk}"
    if pruvodka.drive_date != cr.target_date:
        old_date = cr.target_date
        cr.target_date = pruvodka.drive_date
        update_fields.append("target_date")
        note += (
            f"; termín požadavku posunut z {old_date.strftime('%d.%m.%Y')}"
            f" na {pruvodka.drive_date.strftime('%d.%m.%Y')}"
        )

    cr.planned_pruvodka = pruvodka
    cr.status = CustomerRequest.Status.PLANNED
    cr.save(update_fields=update_fields)

    log_customer_request_action(cr, actor, "planned_from_form", note)
