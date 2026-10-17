"""Přepnutí uzavření druhu vozidla pro den (dispečer)."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser

from catalogs.models import VehicleKindCatalog
from customer_requests.models import CustomerRequestVehicleKindClosure
from waste_docs.customer_request_kind_closure.services.checks import (
    is_vehicle_kind_closed_for_day,
)


def toggle_vehicle_kind_closure(
    user: AbstractBaseUser,
    day: date,
    vehicle_kind_id: int,
) -> bool:
    """Přepne uzavření druhu pro den; vrátí nový stav is_closed."""
    if not VehicleKindCatalog.objects.filter(pk=vehicle_kind_id).exists():
        raise ValueError("Neplatný druh vozidla.")
    new_state = not is_vehicle_kind_closed_for_day(day, vehicle_kind_id)
    row, created = CustomerRequestVehicleKindClosure.objects.get_or_create(
        closure_date=day,
        vehicle_kind_id=vehicle_kind_id,
        defaults={"is_closed": new_state, "updated_by": user},
    )
    if not created:
        row.is_closed = new_state
        row.updated_by = user
        row.save(update_fields=["is_closed", "updated_by", "updated_at"])
    return row.is_closed


__all__ = ["toggle_vehicle_kind_closure"]
