from __future__ import annotations

from django.db.models import Exists, OuterRef, Q

from catalogs.models import DriverAbsence, DriverProfile
from catalogs.services.driver_absence import (
    full_day_absences_on_date,
    partial_absences_on_date,
)
from users.models import UserAccessProfile
from waste_docs.services.svoz_dispatch.dashboard_plan_bridge import driver_ids_with_planned_svoz_slots


def _merge_driver_label(partial_labels: dict[int, str], driver_id: int, label: str) -> None:
    previous = partial_labels.get(driver_id)
    if previous and previous != label:
        partial_labels[driver_id] = f"{previous} · {label}"
    else:
        partial_labels[driver_id] = label


def build_dashboard_drivers_context(selected_date, rides_day_qs) -> dict:
    driver_ids_with_ride = frozenset(
        rides_day_qs.filter(driver_id__isnull=False).values_list("driver_id", flat=True)
    )

    full_day_qs = (
        full_day_absences_on_date(selected_date)
        .select_related("driver")
        .filter(driver_id__isnull=False)
        .order_by("driver__last_name", "driver__first_name", "date_from", "pk")
    )
    # Jiné zůstává v panelu Řidiči — do stripu nepřítomností nepatří.
    strip_absence_qs = full_day_qs.exclude(absence_type=DriverAbsence.AbsenceType.OTHER)
    other_absence_qs = full_day_qs.filter(absence_type=DriverAbsence.AbsenceType.OTHER)

    absence_driver_ids = frozenset(strip_absence_qs.values_list("driver_id", flat=True))
    absence_panel_rows = [
        {"kind": "absence", "absence": a, "driver": a.driver}
        for a in strip_absence_qs
    ]
    legacy_absent = (
        DriverProfile.objects.exclude(Q(availability_note__isnull=True) | Q(availability_note__exact=""))
        .exclude(pk__in=absence_driver_ids)
        .order_by("last_name", "first_name", "personal_number")[:100]
    )
    legacy_absent_ids = frozenset(d.pk for d in legacy_absent if d.pk)
    # Skrýt jen celodenní nepřítomnosti mimo Jiné (+ legacy poznámky).
    hidden_driver_ids = absence_driver_ids.union(legacy_absent_ids)
    portal_linked_sq = UserAccessProfile.objects.filter(driver_profile_id=OuterRef("pk"))
    drivers = list(
        DriverProfile.objects.exclude(pk__in=hidden_driver_ids)
        .annotate(portal_linked=Exists(portal_linked_sq))
        .order_by("last_name", "first_name", "personal_number")[:200]
    )
    partial_labels: dict[int, str] = {}
    for absence in partial_absences_on_date(selected_date):
        if not absence.driver_id:
            continue
        _merge_driver_label(
            partial_labels,
            absence.driver_id,
            f"½ {absence.get_absence_type_display()}",
        )
    for absence in other_absence_qs:
        if not absence.driver_id or absence.driver_id in hidden_driver_ids:
            continue
        note = (absence.note or "").strip()
        if note:
            # Stejný limit jako ve stripu nepřítomností.
            short = note if len(note) <= 80 else (note[:77] + "…")
            label = f"Jiné · {short}"
        else:
            label = "Jiné"
        _merge_driver_label(partial_labels, absence.driver_id, label)
    for driver in drivers:
        driver.partial_absence_label = partial_labels.get(driver.pk, "")
        driver.panel_other_absence = None
    other_by_driver: dict[int, DriverAbsence] = {}
    for absence in other_absence_qs:
        if not absence.driver_id or absence.driver_id in hidden_driver_ids:
            continue
        # První Jiné na den stačí pro edit/smazání z panelu.
        if absence.driver_id not in other_by_driver:
            other_by_driver[absence.driver_id] = absence
    for driver in drivers:
        driver.panel_other_absence = other_by_driver.get(driver.pk)
    for d in legacy_absent:
        absence_panel_rows.append({"kind": "legacy", "driver": d})

    def _absence_panel_sort_key(entry):
        dr = entry.get("driver")
        if dr is None:
            return ("\uffff", "", "")
        return (dr.last_name or "", dr.first_name or "", dr.personal_number or "")

    absence_panel_rows.sort(key=_absence_panel_sort_key)

    planned_svoz_driver_ids = driver_ids_with_planned_svoz_slots(selected_date)

    return {
        "drivers": drivers,
        "driver_ids_with_ride": driver_ids_with_ride,
        "driver_ids_with_planned_svoz": planned_svoz_driver_ids,
        "absence_panel_rows": absence_panel_rows,
        "absence_type_choices": DriverAbsence.AbsenceType.choices,
    }
