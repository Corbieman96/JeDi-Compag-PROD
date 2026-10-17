"""Způsobilí řidiči a RZ pro výměnu podle druhu vozidla skupiny."""

from __future__ import annotations

from catalogs.models import DriverProfile, VehicleRzCatalog, VehicleRzProfile
from waste_docs.models import Pruvodka
from waste_docs.services.svoz_dispatch.driver_vehicle_kind import (
    driver_queryset_for_vehicle_kind,
    rz_valid_for_vehicle_kind,
    vehicle_rz_queryset_for_vehicle_kind,
)


def resolve_vehicle_kind_id_for_rides(rides: list[Pruvodka]) -> int | None:
    """Preferovat druh z pasportu; jinak první druh z profilu RZ."""
    for ride in rides:
        vk_id = getattr(getattr(ride, "container_passport", None), "vehicle_kind_id", None)
        if vk_id:
            return int(vk_id)
    for ride in rides:
        rz = getattr(ride, "vehicle_rz", None)
        prof = getattr(rz, "profile", None) if rz else None
        if not prof:
            continue
        kinds = list(prof.vehicle_kinds.all())
        if kinds:
            kinds.sort(key=lambda k: (k.sort_order, k.name or "", k.pk))
            return int(kinds[0].pk)
    return None


def eligible_drivers_for_kind(vehicle_kind_id: int) -> list[DriverProfile]:
    return list(
        driver_queryset_for_vehicle_kind(int(vehicle_kind_id)).prefetch_related(
            "allowed_vehicle_kinds",
            "allowed_vehicle_rz",
            "allowed_vehicle_rz__rz",
            "allowed_vehicle_rz__vehicle_kinds",
        )
    )


def driver_allowed_kind_ids(driver: DriverProfile) -> set[int]:
    ids = {int(pk) for pk in driver.allowed_vehicle_kinds.values_list("pk", flat=True)}
    for prof in driver.allowed_vehicle_rz.all():
        ids.update(int(k.pk) for k in prof.vehicle_kinds.all())
    return ids


def eligible_rz_for_driver(driver: DriverProfile) -> list[VehicleRzCatalog]:
    """Všechny RZ všech druhů, které řidič smí řídit — ne jen párované SPZ."""
    kind_ids = driver_allowed_kind_ids(driver)
    if not kind_ids:
        return []
    seen: dict[int, VehicleRzCatalog] = {}
    for kid in kind_ids:
        for rz in vehicle_rz_queryset_for_vehicle_kind(int(kid)).prefetch_related(
            "profile__vehicle_kinds"
        ):
            seen[int(rz.pk)] = rz
    return sorted(seen.values(), key=lambda r: ((r.value or "").lower(), r.pk))


def rz_matches_driver_kinds(driver: DriverProfile, vehicle_rz_id: int) -> bool:
    kind_ids = driver_allowed_kind_ids(driver)
    if not kind_ids:
        return False
    return any(rz_valid_for_vehicle_kind(int(vehicle_rz_id), int(kid)) for kid in kind_ids)


def _driver_short_name(driver: DriverProfile) -> str:
    last = (driver.last_name or "").strip()
    if last:
        return last
    full = " ".join(
        part for part in [driver.title, driver.first_name, driver.last_name] if part
    ).strip()
    return full or (driver.personal_number or str(driver.pk))


def format_rz_option_label(
    rz: VehicleRzCatalog,
    *,
    eligible_drivers: list[DriverProfile] | None = None,
) -> str:
    """Stejný styl jako průvodka: RZ - poznámka | Druh: zkratky · řidiči."""
    value = (rz.value or "").strip() or str(rz.pk)
    prof: VehicleRzProfile | None = getattr(rz, "profile", None)
    note = ""
    kinds = ""
    if prof is not None:
        note = (prof.vehicle_type or "").strip()
        shortcuts = [
            (k.shortcut or "").strip()
            for k in sorted(
                prof.vehicle_kinds.all(),
                key=lambda k: (k.sort_order, k.name or "", k.pk),
            )
            if (k.shortcut or "").strip()
        ]
        kinds = ", ".join(shortcuts)
    details = " | ".join(part for part in [note, f"Druh: {kinds}" if kinds else ""] if part)
    label = f"{value} - {details}" if details else value

    if eligible_drivers:
        names: list[str] = []
        for d in eligible_drivers:
            allowed = list(d.allowed_vehicle_rz.all())
            if not allowed:
                # prázdné M2M = smí libovolnou RZ daného druhu — neuvádět u všech RZ
                continue
            if any(p.rz_id == rz.pk for p in allowed):
                names.append(_driver_short_name(d))
        if names:
            label = f"{label} · {', '.join(names)}"
    return label


def format_driver_option_label(driver: DriverProfile, rz_values: list[str]) -> str:
    base = str(driver)
    rz_part = ", ".join(v for v in rz_values if v)
    if rz_part:
        return f"{base} · {rz_part}"
    return base


def driver_rz_options_map(
    *,
    drivers: list[DriverProfile],
) -> dict[int, list[dict]]:
    """driver_id -> [{id, label}, ...] pro JS filtr selectu RZ (všechny druhy řidiče)."""
    out: dict[int, list[dict]] = {}
    for driver in drivers:
        rzs = eligible_rz_for_driver(driver)
        out[int(driver.pk)] = [
            {
                "id": int(rz.pk),
                "value": (rz.value or "").strip() or str(rz.pk),
                "label": format_rz_option_label(rz, eligible_drivers=drivers),
            }
            for rz in rzs
        ]
    return out


def validate_driver_and_rz(
    *,
    driver_id: int,
    vehicle_rz_id: int,
    vehicle_kind_id: int,
) -> str | None:
    eligible_ids = set(
        driver_queryset_for_vehicle_kind(int(vehicle_kind_id)).values_list("pk", flat=True)
    )
    if int(driver_id) not in eligible_ids:
        return (
            "Vybraný řidič nemá v číselníku povolený tento druh vozidla "
            "(doplňte druhy vozidel u řidiče nebo profil RZ)."
        )
    driver = (
        DriverProfile.objects.filter(pk=int(driver_id))
        .prefetch_related(
            "allowed_vehicle_kinds",
            "allowed_vehicle_rz",
            "allowed_vehicle_rz__vehicle_kinds",
        )
        .first()
    )
    if not driver or not rz_matches_driver_kinds(driver, int(vehicle_rz_id)):
        return "Vybrané RZ neodpovídá druhům vozidla, které řidič smí řídit."
    return None
