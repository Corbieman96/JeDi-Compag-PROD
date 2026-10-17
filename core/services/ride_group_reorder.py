"""Ruční pořadí zastávek v jízdě na dashboardu — bez změny SND."""

from __future__ import annotations

from datetime import date

from django.db import transaction

from waste_docs.models import Pruvodka


def queryset_for_dashboard_ride_group(
    *,
    drive_date: date,
    vehicle_rz_id: int | None,
    driver_id: int | None,
):
    qs = Pruvodka.objects.filter(drive_date=drive_date, is_archived=False)
    if vehicle_rz_id:
        qs = qs.filter(vehicle_rz_id=vehicle_rz_id)
    else:
        qs = qs.filter(vehicle_rz_id__isnull=True)
    if driver_id:
        qs = qs.filter(driver_id=driver_id)
    else:
        qs = qs.filter(driver_id__isnull=True)
    return qs


def ride_group_has_mixed_snd_groups(items: list[Pruvodka]) -> bool:
    nums = {int(r.ride_group_number or 0) for r in items if int(r.ride_group_number or 0) > 0}
    return len(nums) > 1


def reorder_ride_group_items(
    *,
    drive_date: date,
    vehicle_rz_id: int | None,
    driver_id: int | None,
    ordered_pks: list[int],
) -> tuple[int, list[str]]:
    """
    Nastaví ride_route_order 1..N podle ordered_pks. SND a ride_sequence nemění.
    Vrací (počet změněných záznamů, varování).
    """
    warnings: list[str] = []
    with transaction.atomic():
        qs = queryset_for_dashboard_ride_group(
            drive_date=drive_date,
            vehicle_rz_id=vehicle_rz_id,
            driver_id=driver_id,
        )
        by_pk = {p.pk: p for p in qs.select_for_update()}
        expected_pks = set(by_pk.keys())
        if not expected_pks:
            return 0, ["Skupina jízdy neobsahuje žádné průvodky."]

        if len(ordered_pks) != len(expected_pks):
            return 0, ["Pořadí musí obsahovat všechny průvodky ve skupině."]
        if set(ordered_pks) != expected_pks:
            return 0, ["Neplatná sada průvodek pro tuto jízdu."]

        changed = 0
        for idx, pk in enumerate(ordered_pks, start=1):
            ride = by_pk[pk]
            if ride.ride_route_order != idx:
                ride.ride_route_order = idx
                ride.save(update_fields=["ride_route_order"])
                changed += 1

    if ride_group_has_mixed_snd_groups(list(by_pk.values())):
        warnings.append(
            "Ve skupině jsou smíchaná kmenová čísla SND — pořadí trasy se mění, "
            "čísla na průvodkách zůstávají beze změny."
        )
    return changed, warnings


def reset_ride_group_route_order(
    *,
    drive_date: date,
    vehicle_rz_id: int | None,
    driver_id: int | None,
) -> int:
    """Vrátí ruční pořadí (ride_route_order = 0) u celé skupiny."""
    qs = queryset_for_dashboard_ride_group(
        drive_date=drive_date,
        vehicle_rz_id=vehicle_rz_id,
        driver_id=driver_id,
    )
    return qs.filter(ride_route_order__gt=0).update(ride_route_order=0)
