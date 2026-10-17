"""Popisy kontejnerů z pasportu pro AI prompt."""

from __future__ import annotations

from catalogs.models import ContainerPassport
from waste_docs.models import Pruvodka


def format_container_for_prompt(number: str, passport: ContainerPassport | None) -> str:
    num = (number or "").strip()
    if not num:
        return ""
    if passport is None:
        return num
    parts = [num, "VOK"]
    if passport.volume_m3 is not None:
        vol = passport.volume_m3
        vol_str = f"{vol:.0f}" if vol == vol.to_integral_value() else f"{vol:.2f}".rstrip("0").rstrip(".")
        parts.append(f"{vol_str} m³")
    if passport.vehicle_kind_id:
        kind_name = (getattr(passport.vehicle_kind, "name", None) or "").strip()
        if kind_name:
            parts.append(f"druh vozidla: {kind_name}")
    note = (passport.vehicle_requirement_note or "").strip()
    if note:
        parts.append(note)
    return " ".join(parts)


def load_passport_map(numbers: set[str]) -> dict[str, ContainerPassport]:
    if not numbers:
        return {}
    passports = ContainerPassport.objects.filter(container_number__in=numbers).select_related(
        "vehicle_kind"
    )
    return {p.container_number: p for p in passports}


def format_ride_containers_for_prompt(
    ride: Pruvodka,
    passport_map: dict[str, ContainerPassport],
) -> str:
    labels: list[str] = []
    for num in [(ride.container_number or "").strip(), (ride.container_number_2 or "").strip()]:
        if not num:
            continue
        passport = None
        if ride.container_passport_id and (ride.container_number or "").strip() == num:
            passport = ride.container_passport
        if passport is None:
            passport = passport_map.get(num)
        label = format_container_for_prompt(num, passport)
        if label:
            labels.append(label)
    return " + ".join(labels) if labels else "—"
