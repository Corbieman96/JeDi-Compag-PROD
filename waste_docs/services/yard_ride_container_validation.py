"""Validace čísla kontejneru při založení průvodky ze sběrného dvora (pasport × pár × vybraná RZ)."""

from __future__ import annotations

from datetime import date

from catalogs.models import ContainerPassport, NameSubjectProfile, NameSubjectWasteSuffixPair, VehicleRzCatalog
from catalogs.services.name_subject_pair_vehicle_kinds import (
    pair_has_vehicle_kinds,
    pair_vehicle_kind_ids,
    pair_vehicle_kinds_display,
)
from catalogs.services.vehicle_kind_compatibility import passport_kind_valid_for_task
from waste_docs.services.container_passport_ride_validation import (
    normalize_container_number,
    passport_by_container_number,
    passport_matches_vehicle_rz,
)

_CONTACT_DISPATCH_SUFFIX = (
    " Pokud problém nevyřešíte sami, kontaktujte dispečera nebo vedoucího."
)


def _single_container_fragment(raw: str) -> tuple[str | None, str | None]:
    """Vrátí (normalizované číslo, chyba) — povoleno jen jedno číslo."""
    text = (raw or "").replace(";", ",")
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return None, None
    if len(parts) > 1:
        return None, "Zadejte pouze jedno číslo kontejneru."
    return normalize_container_number(parts[0]), None


def yard_ride_container_blocking_error(
    *,
    subject: NameSubjectProfile,
    pair: NameSubjectWasteSuffixPair,
    container_number: str,
    vehicle_rz_id: int,
    target_date: date,
) -> str | None:
    """
    Pokud číslo nesedí k pasportu, druhu vozidla řádku nebo vybrané RZ,
    vrátí text chyby (odeslání formuláře se má zastavit).
    """
    num, multi_err = _single_container_fragment(container_number)
    if multi_err:
        return multi_err
    if not num or not pair_has_vehicle_kinds(pair):
        return None

    label = (pair.yard_svoz_display_label or "").strip() or "řádek"
    passport: ContainerPassport | None = passport_by_container_number(num)
    if not passport:
        return (
            f"{label}: kontejner {num} není v číselníku pasportů. "
            "Založte ho v Číselníky → Pasport kontejnerů (/catalogs/container-passport/)."
            f"{_CONTACT_DISPATCH_SUFFIX}"
        )

    vk_disp = pair_vehicle_kinds_display(pair) or "řádek matice"
    kind_ids = pair_vehicle_kind_ids(pair)

    if not any(
        passport_kind_valid_for_task(passport.vehicle_kind_id, vk_id) for vk_id in kind_ids
    ):
        p_vk = passport.vehicle_kind
        p_disp = p_vk.display_label() if p_vk else "jiný druh"
        return (
            f"{label}: kontejner {num} je v pasportech pod druhem {p_disp}, "
            f"řádek matice povoluje {vk_disp}. Upravte pasport nebo číslo kontejneru."
            f"{_CONTACT_DISPATCH_SUFFIX}"
        )

    rz = VehicleRzCatalog.objects.filter(pk=vehicle_rz_id).select_related("profile").first()
    if rz:
        rz_ok = any(
            passport_matches_vehicle_rz(passport, rz, task_kind_id=vk_id) for vk_id in kind_ids
        )
        if not rz_ok:
            return (
                f"{label}: kontejner {num} je v pasportech evidován pod jiným druhem vozidla, "
                f"než odpovídá RZ {rz.value} a {vk_disp}. "
                f"Opravte pasport v Číselníky → Pasport kontejnerů, nebo zadejte jiné číslo kontejneru."
                f"{_CONTACT_DISPATCH_SUFFIX}"
            )

    return None


__all__ = ["yard_ride_container_blocking_error"]
