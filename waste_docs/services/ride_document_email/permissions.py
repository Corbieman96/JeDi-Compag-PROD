from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser

from users.services.access import can_see_all_waste_docs
from waste_docs.models import Pruvodka


def user_may_email_group(
    user: AbstractBaseUser,
    *,
    drive_date: date,
    vehicle_rz_id: int,
    driver_id: int | None = None,
    filter_pks: list[int] | None = None,
) -> bool:
    if vehicle_rz_id <= 0:
        return False
    qs = Pruvodka.objects.filter(
        drive_date=drive_date,
        vehicle_rz_id=vehicle_rz_id,
        is_archived=False,
    )
    if driver_id is not None and not filter_pks:
        if driver_id > 0:
            qs = qs.filter(driver_id=driver_id)
        else:
            qs = qs.filter(driver_id__isnull=True)
    if filter_pks:
        qs = qs.filter(pk__in=filter_pks)
    if not can_see_all_waste_docs(user):
        qs = qs.filter(created_by=user)
    return qs.exists()
