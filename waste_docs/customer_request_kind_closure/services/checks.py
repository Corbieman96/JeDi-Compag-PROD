"""Kontrola, zda je druh vozidla pro den uzavřený pro nové požadavky."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser

from catalogs.models import VehicleKindCatalog
from customer_requests.models import CustomerRequestVehicleKindClosure
from waste_docs.services.customer_request_date_closure import (
    can_bypass_date_closure,
    is_target_date_closed,
)


def is_vehicle_kind_closed_for_day(day: date | None, vehicle_kind_id: int | None) -> bool:
    """True, pokud dispečer uzavřel konkrétní druh pro daný den."""
    if not day or not vehicle_kind_id:
        return False
    return CustomerRequestVehicleKindClosure.objects.filter(
        closure_date=day,
        vehicle_kind_id=int(vehicle_kind_id),
        is_closed=True,
    ).exists()


def vehicle_kind_closure_error(
    day: date | None,
    vehicle_kind_id: int | None,
    *,
    user: AbstractBaseUser | None = None,
) -> str | None:
    """
    Chybová hláška při pokusu zadat požadavek na uzavřený druh.

    Celodenní uzávěrka se řeší zvlášť (`target_date_closure_error`) — tady jen druh.
    """
    if not day or not vehicle_kind_id or can_bypass_date_closure(user):
        return None
    if is_target_date_closed(day):
        return None
    if not is_vehicle_kind_closed_for_day(day, vehicle_kind_id):
        return None
    kind = (
        VehicleKindCatalog.objects.filter(pk=int(vehicle_kind_id))
        .only("name", "shortcut")
        .first()
    )
    label = kind.display_label() if kind else str(vehicle_kind_id)
    return (
        f"Pro druh vozidla {label} je tento den uzavřen. Zvolte jiné datum."
    )


__all__ = [
    "is_vehicle_kind_closed_for_day",
    "vehicle_kind_closure_error",
]
