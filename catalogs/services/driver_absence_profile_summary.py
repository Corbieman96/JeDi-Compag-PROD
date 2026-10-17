"""Souhrn a metadata kalendářové nepřítomnosti pro stránku úpravy řidiče."""

from __future__ import annotations

from datetime import date

from catalogs.models import DriverAbsence, DriverProfile


def absence_years_for_driver(driver_id: int) -> list[int]:
    """Roky, ve kterých řidič má alespoň jeden záznam nepřítomnosti (sestupně)."""
    years: set[int] = set()
    for date_from, date_to in DriverAbsence.objects.filter(driver_id=driver_id).values_list(
        "date_from", "date_to"
    ):
        if date_from:
            years.add(date_from.year)
        if date_to:
            years.add(date_to.year)
    return sorted(years, reverse=True)


def active_absence_on_date(driver: DriverProfile, on_date: date) -> DriverAbsence | None:
    """První záznam nepřítomnosti pokrývající daný den, nebo None."""
    return (
        driver.absences.filter(date_from__lte=on_date, date_to__gte=on_date)
        .order_by("-date_from", "-pk")
        .first()
    )


def absence_total_count_for_driver(driver_id: int) -> int:
    return DriverAbsence.objects.filter(driver_id=driver_id).count()
