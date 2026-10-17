from __future__ import annotations

from datetime import date

from waste_docs.models.ride_group_email_dispatch import RideGroupEmailDispatch


def is_group_emailed(drive_date: date, vehicle_rz_id: int) -> bool:
    if not vehicle_rz_id:
        return False
    return RideGroupEmailDispatch.objects.filter(
        drive_date=drive_date,
        vehicle_rz_id=vehicle_rz_id,
    ).exists()


def emailed_vehicle_rz_ids_for_date(drive_date: date) -> frozenset[int]:
    return frozenset(
        RideGroupEmailDispatch.objects.filter(drive_date=drive_date).values_list(
            "vehicle_rz_id",
            flat=True,
        )
    )
