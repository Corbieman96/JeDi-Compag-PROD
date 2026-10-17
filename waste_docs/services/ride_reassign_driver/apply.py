"""Aplikace hromadné výměny řidiče / RZ."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.urls import reverse

from catalogs.models import DriverProfile, VehicleRzCatalog
from core.services.ride_grouping import ride_group_key
from users.services.waste_doc_permissions import can_edit_existing_pruvodka
from waste_docs.services.ride_numbering import apply_pruvodka_catalog_snapshots
from waste_docs.services.ride_reassign_driver.eligibility import (
    resolve_vehicle_kind_id_for_rides,
    validate_driver_and_rz,
)
from waste_docs.services.ride_reassign_driver.peers import peer_pk_set, peers_for_reassign


@dataclass(frozen=True)
class RideReassignResult:
    ok: bool
    message: str
    updated_count: int = 0
    redirect_url: str = ""


def apply_ride_reassign_driver(
    *,
    user: AbstractBaseUser,
    drive_date: date,
    from_vehicle_rz_id: int | None,
    from_driver_id: int | None,
    selected_pks: list[int],
    new_driver_id: int,
    new_vehicle_rz_id: int | None,
) -> RideReassignResult:
    if not selected_pks:
        return RideReassignResult(ok=False, message="Vyberte alespoň jednu jízdu.")
    if not new_driver_id:
        return RideReassignResult(ok=False, message="Vyberte nového řidiče.")

    peers = peers_for_reassign(
        drive_date=drive_date,
        vehicle_rz_id=from_vehicle_rz_id,
        driver_id=from_driver_id,
        user=user,
    )
    allowed = peer_pk_set(peers)
    selected = [int(pk) for pk in selected_pks]
    if not selected or any(pk not in allowed for pk in selected):
        return RideReassignResult(
            ok=False,
            message="Některé vybrané jízdy nepatří do této skupiny nebo je nemáte k dispozici.",
        )

    rides = [r for r in peers if r.pk in set(selected)]
    kind_id = resolve_vehicle_kind_id_for_rides(rides)
    if not kind_id:
        return RideReassignResult(
            ok=False,
            message="U skupiny nelze určit druh vozidla (chybí profil RZ nebo pasport).",
        )

    target_rz_id = int(new_vehicle_rz_id) if new_vehicle_rz_id else int(from_vehicle_rz_id or 0)
    if not target_rz_id:
        return RideReassignResult(ok=False, message="Chybí RZ vozidla.")

    same_driver = int(new_driver_id) == int(from_driver_id or 0)
    same_rz = target_rz_id == int(from_vehicle_rz_id or 0)
    if same_driver and same_rz:
        return RideReassignResult(
            ok=False,
            message="Vyberte jiného řidiče nebo jinou RZ — nic se nezměnilo.",
        )

    err = validate_driver_and_rz(
        driver_id=int(new_driver_id),
        vehicle_rz_id=target_rz_id,
        vehicle_kind_id=int(kind_id),
    )
    if err:
        return RideReassignResult(ok=False, message=err)

    for ride in rides:
        if not can_edit_existing_pruvodka(user, ride):
            return RideReassignResult(
                ok=False,
                message=f"Nemáte oprávnění upravit jízdu #{ride.pk}.",
            )
        if ride.is_archived:
            return RideReassignResult(
                ok=False,
                message=f"Jízda #{ride.pk} je archivovaná a nelze ji měnit.",
            )

    new_driver = DriverProfile.objects.get(pk=int(new_driver_id))
    new_rz = VehicleRzCatalog.objects.get(pk=target_rz_id)

    with transaction.atomic():
        for ride in rides:
            ride.driver = new_driver
            ride.vehicle_rz = new_rz
            apply_pruvodka_catalog_snapshots(ride)
            ride.save(
                update_fields=[
                    "driver",
                    "vehicle_rz",
                    "driver_snapshot",
                    "vehicle_rz_snapshot",
                    "updated_at",
                ]
            )

    new_key = ride_group_key(drive_date, target_rz_id, int(new_driver_id))
    redirect_url = (
        f"{reverse('core:dashboard')}?date={drive_date.isoformat()}&ride_group={new_key}"
    )
    n = len(rides)
    return RideReassignResult(
        ok=True,
        message=f"Upraveno jízd: {n} (řidič / RZ).",
        updated_count=n,
        redirect_url=redirect_url,
    )
