"""Logika kalendářové nepřítomnosti řidičů (plný den vs. půlden)."""

from __future__ import annotations

from datetime import date
from typing import FrozenSet

from catalogs.models import DriverAbsence


def full_day_absences_on_date(on_date: date):
    """Záznamy, které v daný den znamenají celodenní nepřítomnost (řidič mimo provoz)."""
    return DriverAbsence.objects.filter(
        date_from__lte=on_date,
        date_to__gte=on_date,
        is_partial=False,
    )


def partial_absences_on_date(on_date: date):
    """Půldenní nepřítomnost v daný den — řidič zůstane v panelu Řidiči."""
    return DriverAbsence.objects.filter(
        date_from__lte=on_date,
        date_to__gte=on_date,
        is_partial=True,
    )


def driver_ids_fully_absent_on_date(on_date: date) -> FrozenSet[int]:
    ids = full_day_absences_on_date(on_date).values_list("driver_id", flat=True).distinct()
    return frozenset(int(pk) for pk in ids)


def driver_ids_hidden_from_drivers_panel(on_date: date) -> FrozenSet[int]:
    """
    Stejná množina jako dashboard panel Nepřítomnost:
    celodenní absence mimo typ Jiné + legacy availability_note.
    (Jiné a půlden zůstávají v panelu Řidiči.)
    """
    from django.db.models import Q

    from catalogs.models import DriverProfile

    strip_ids = frozenset(
        int(pk)
        for pk in full_day_absences_on_date(on_date)
        .exclude(absence_type=DriverAbsence.AbsenceType.OTHER)
        .filter(driver_id__isnull=False)
        .values_list("driver_id", flat=True)
        if pk
    )
    legacy_ids = frozenset(
        DriverProfile.objects.exclude(
            Q(availability_note__isnull=True) | Q(availability_note__exact="")
        )
        .exclude(pk__in=strip_ids)
        .values_list("pk", flat=True)
    )
    return strip_ids.union(legacy_ids)
