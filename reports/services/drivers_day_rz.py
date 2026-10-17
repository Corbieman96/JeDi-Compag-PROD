"""Výpis vytížení řidičů: den + RZ (typ vozidla) v období reportu."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db.models import Prefetch

from catalogs.models import VehicleRzCatalog, VehicleRzProfile
from reports.services.date_range import ReportDateRange
from waste_docs.models import Pruvodka


@dataclass(frozen=True)
class DriversDayRzRow:
    driver_label: str
    drive_date: date
    date_label: str
    vehicle_type: str
    rz: str


def _driver_label_from_parts(last_name: str, first_name: str, personal_number: str) -> str:
    name = " ".join(p for p in [last_name or "", first_name or ""] if p).strip()
    return name or (personal_number or "").strip() or "—"


def _date_label(d: date) -> str:
    return f"{d.day}. {d.month}. {d.year}"


def _vehicle_type_for_rz(rz: VehicleRzCatalog | None) -> str:
    """Druh vozidla z katalogu (Řetěz, Hák…), ne volná poznámka Typ vozidla u RZ."""
    if rz is None:
        return "—"
    try:
        profile = rz.profile
    except VehicleRzProfile.DoesNotExist:
        return "—"
    kinds = list(profile.vehicle_kinds.all())
    if kinds:
        labels = []
        for kind in kinds:
            label = (kind.name or kind.shortcut or "").strip()
            if label:
                labels.append(label)
        if labels:
            return ", ".join(labels)
    # Fallback jen když u RZ nejsou druhy
    vtype = (profile.vehicle_type or "").strip()
    return vtype or "—"


def build_drivers_day_rz_rows(date_range: ReportDateRange) -> list[DriversDayRzRow]:
    """
    Unikátní trojice řidič + den + RZ. Více RZ za den = více řádků pod sebou.
    """
    qs = (
        Pruvodka.objects.filter(
            is_archived=False,
            drive_date__gte=date_range.date_from,
            drive_date__lte=date_range.date_to,
            driver__isnull=False,
        )
        .exclude(vehicle_rz__isnull=True, vehicle_rz_snapshot="")
        .select_related("driver", "vehicle_rz", "vehicle_rz__profile")
        .prefetch_related(
            Prefetch(
                "vehicle_rz__profile__vehicle_kinds",
            )
        )
        .order_by(
            "drive_date",
            "driver__last_name",
            "driver__first_name",
            "vehicle_rz__value",
            "vehicle_rz_snapshot",
            "pk",
        )
    )

    seen: set[tuple[int, date, str]] = set()
    rows: list[DriversDayRzRow] = []
    for ride in qs:
        rz_value = ""
        if ride.vehicle_rz_id and ride.vehicle_rz:
            rz_value = (ride.vehicle_rz.value or "").strip()
        if not rz_value:
            rz_value = (ride.vehicle_rz_snapshot or "").strip()
        if not rz_value:
            continue
        key = (ride.driver_id, ride.drive_date, rz_value.casefold())
        if key in seen:
            continue
        seen.add(key)
        driver = ride.driver
        rows.append(
            DriversDayRzRow(
                driver_label=_driver_label_from_parts(
                    driver.last_name if driver else "",
                    driver.first_name if driver else "",
                    driver.personal_number if driver else "",
                ),
                drive_date=ride.drive_date,
                date_label=_date_label(ride.drive_date),
                vehicle_type=_vehicle_type_for_rz(ride.vehicle_rz),
                rz=rz_value,
            )
        )
    return rows
