"""Peer jízdy skupiny (den + RZ + řidič)."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser

from core.services.ride_group_reorder import queryset_for_dashboard_ride_group
from users.services.access import can_see_all_waste_docs
from waste_docs.models import Pruvodka
from waste_docs.services.ride_print_order import order_rides_queryset


def peers_for_reassign(
    *,
    drive_date: date,
    vehicle_rz_id: int | None,
    driver_id: int | None,
    user: AbstractBaseUser,
) -> list[Pruvodka]:
    qs = queryset_for_dashboard_ride_group(
        drive_date=drive_date,
        vehicle_rz_id=vehicle_rz_id,
        driver_id=driver_id,
    )
    if not can_see_all_waste_docs(user):
        qs = qs.filter(created_by=user)
    return list(
        order_rides_queryset(
            qs.select_related(
                "activity",
                "driver",
                "vehicle_rz",
                "vehicle_rz__profile",
                "container_passport",
                "container_passport__vehicle_kind",
            ).prefetch_related("vehicle_rz__profile__vehicle_kinds")
        )
    )


def peer_pk_set(peers: list[Pruvodka]) -> set[int]:
    return {int(r.pk) for r in peers}
