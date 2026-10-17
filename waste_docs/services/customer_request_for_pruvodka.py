"""Zdrojový zákaznický požadavek pro jízdu založenou přes dispatch."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import Q

from customer_requests.models import CustomerRequest
from users.constants import ROLE_ZADAVATEL
from users.services.access import app_role
from waste_docs.models import Pruvodka


def source_customer_request_for_pruvodka(pruvodka: Pruvodka) -> CustomerRequest | None:
    pk = pruvodka.pk
    return (
        CustomerRequest.objects.filter(
            Q(planned_pruvodka_id=pk) | Q(planned_follow_up_pruvodka_id=pk)
        )
        .select_related("name", "activity", "created_by")
        .order_by("-pk")
        .first()
    )


def can_view_customer_request(user: AbstractBaseUser, item: CustomerRequest) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if app_role(user) == ROLE_ZADAVATEL and item.created_by_id != user.pk:
        return False
    return True
