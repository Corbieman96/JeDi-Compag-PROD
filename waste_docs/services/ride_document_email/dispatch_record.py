from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser

from waste_docs.models.ride_group_email_dispatch import RideGroupEmailDispatch


def get_group_dispatch(drive_date: date, vehicle_rz_id: int) -> RideGroupEmailDispatch | None:
    if not vehicle_rz_id:
        return None
    return RideGroupEmailDispatch.objects.filter(
        drive_date=drive_date,
        vehicle_rz_id=vehicle_rz_id,
    ).first()


def group_dispatch_map_for_date(drive_date: date) -> dict[int, RideGroupEmailDispatch]:
    rows = RideGroupEmailDispatch.objects.filter(drive_date=drive_date).select_related(
        "vehicle_rz",
        "dispatched_by",
    )
    return {row.vehicle_rz_id: row for row in rows}


def record_group_dispatch(
    *,
    drive_date: date,
    vehicle_rz_id: int,
    recipient_email: str,
    subject: str,
    ride_count: int,
    attachment_count: int,
    user: AbstractBaseUser,
) -> RideGroupEmailDispatch:
    obj, _created = RideGroupEmailDispatch.objects.update_or_create(
        drive_date=drive_date,
        vehicle_rz_id=vehicle_rz_id,
        defaults={
            "recipient_email": recipient_email,
            "subject": subject[:255],
            "ride_count": ride_count,
            "attachment_count": attachment_count,
            "dispatched_by": user,
        },
    )
    return obj


def cancel_group_dispatch(drive_date: date, vehicle_rz_id: int) -> bool:
    deleted, _ = RideGroupEmailDispatch.objects.filter(
        drive_date=drive_date,
        vehicle_rz_id=vehicle_rz_id,
    ).delete()
    return bool(deleted)
