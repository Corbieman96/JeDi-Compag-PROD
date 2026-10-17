from __future__ import annotations

from waste_docs.models import Pruvodka

RIDE_PRINT_ORDER_FIELDS = (
    "vehicle_rz_snapshot",
    "driver_snapshot",
    "ride_route_order",
    "ride_group_number",
    "ride_sequence",
    "snd_cislo_listu",
    "pk",
)


def ride_print_sort_key(ride: Pruvodka) -> tuple:
    base = (
        (ride.vehicle_rz_snapshot or "").strip(),
        (ride.driver_snapshot or "").strip(),
    )
    manual = int(getattr(ride, "ride_route_order", 0) or 0)
    if manual > 0:
        return base + (0, manual, ride.pk or 0)
    return base + (
        1,
        ride.ride_group_number or 0,
        ride.ride_sequence or 0,
        (ride.snd_cislo_listu or "").strip(),
        ride.pk or 0,
    )


def order_rides_queryset(qs):
    return qs.order_by(*RIDE_PRINT_ORDER_FIELDS)


def sort_rides_list(rides: list[Pruvodka]) -> list[Pruvodka]:
    return sorted(rides, key=ride_print_sort_key)
