from __future__ import annotations

from datetime import date

from waste_docs.models import Pruvodka


def pruvodky_queryset_for_driver_day(driver_id: int, day: date):
    return (
        Pruvodka.objects.filter(driver_id=driver_id, drive_date=day, is_archived=False)
        .select_related("address", "name", "waste_type", "activity")
        .order_by("snd_cislo_listu", "ride_sequence", "ride_group_number", "pk")
    )
