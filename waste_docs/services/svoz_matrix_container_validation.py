"""Validace čísla kontejneru v matici požadavku před odesláním (pasport × druh vozidla / RZ z plánu)."""

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
from waste_docs.services.svoz_dispatch.matrix_plan_match import planned_driver_and_rz_for_matrix_pair
from waste_docs.services.svoz_matrix_container_entries import non_empty_container_entries
from waste_docs.services.svoz_task_dedup import (
    find_active_pruvodka_for_yard_container,
    find_done_svoz_task_for_yard_container,
    find_open_svoz_task_for_line,
    find_open_svoz_task_for_yard_container,
)

_CONTACT_DISPATCH_SUFFIX = (
    " Pokud problém nevyřešíte sami, kontaktujte dispečera nebo vedoucího."
)


def _primary_container_fragment(raw: str) -> str:
    text = (raw or "").replace(";", ",")
    parts = [p.strip() for p in text.split(",") if p.strip()]
    return parts[0] if parts else ""


def _pair_label(pair: NameSubjectWasteSuffixPair) -> str:
    return (pair.yard_svoz_display_label or "").strip() or "řádek"


def _matrix_container_in_use_error(
    *,
    subject: NameSubjectProfile,
    pair: NameSubjectWasteSuffixPair,
    label: str,
    num: str,
    target_date: date,
) -> str | None:
    n = normalize_container_number(num)
    if not n:
        return None

    if find_active_pruvodka_for_yard_container(
        subject_profile=subject,
        container_number=n,
        drive_date=target_date,
    ) or find_done_svoz_task_for_yard_container(
        subject_profile_id=subject.pk,
        container_number=n,
        target_date=target_date,
    ):
        return (
            f"{label}: kontejner {n} už má na tento den zadaný požadavek nebo jízdu. "
            f"Duplicitní hlášení není potřeba."
            f"{_CONTACT_DISPATCH_SUFFIX}"
        )

    if find_open_svoz_task_for_line(
        subject_profile_id=subject.pk,
        pair_id=pair.pk,
        container_number=n,
        target_date=target_date,
    ):
        return None

    if find_open_svoz_task_for_yard_container(
        subject_profile_id=subject.pk,
        container_number=n,
        target_date=target_date,
    ):
        return (
            f"{label}: kontejner {n} je již na otevřeném požadavku svozu pro tento den "
            f"u jiného řádku matice. Počkejte na vyřízení nebo zadejte jiný kontejner."
            f"{_CONTACT_DISPATCH_SUFFIX}"
        )

    return None


def matrix_unknown_passport_number(
    *,
    pair: NameSubjectWasteSuffixPair,
    container_numbers: str,
) -> str | None:
    """Normalizované číslo, pokud není v číselníku pasportů; jinak None."""
    num = normalize_container_number(_primary_container_fragment(container_numbers))
    if not num or not pair_has_vehicle_kinds(pair):
        return None
    if passport_by_container_number(num):
        return None
    return num


def matrix_unknown_passport_log_message(*, pair: NameSubjectWasteSuffixPair, num: str) -> str:
    label = _pair_label(pair)
    return (
        f"{label}: kontejner {num} není v číselníku pasportů. "
        "Založte ho v Číselníky → Pasport kontejnerů (/catalogs/container-passport/)."
        f"{_CONTACT_DISPATCH_SUFFIX}"
    )


def matrix_unknown_passport_numbers_for_field(
    *,
    pair: NameSubjectWasteSuffixPair,
    container_field_raw: str,
) -> list[str]:
    """Neznámá čísla v textarea (pořadí zachováno, bez duplicit)."""
    seen: set[str] = set()
    out: list[str] = []
    for one_line in non_empty_container_entries(container_field_raw):
        num = matrix_unknown_passport_number(pair=pair, container_numbers=one_line)
        if not num or num in seen:
            continue
        seen.add(num)
        out.append(num)
    return out


def matrix_container_passport_blocking_error(
    *,
    subject: NameSubjectProfile,
    pair: NameSubjectWasteSuffixPair,
    container_numbers: str,
    target_date: date,
) -> str | None:
    """
    Blokující chyby pasportu (odeslání zastavit).
    Neznámé číslo v číselníku sem nepatří — řeší se potvrzením při odeslání.
    """
    num = _primary_container_fragment(container_numbers)
    num = normalize_container_number(num)
    if not num or not pair_has_vehicle_kinds(pair):
        return None

    label = _pair_label(pair)
    passport: ContainerPassport | None = passport_by_container_number(num)
    if not passport:
        return None

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

    _driver_id, rz_id, matched_vk_id = planned_driver_and_rz_for_matrix_pair(subject, pair, target_date)
    if rz_id:
        rz = VehicleRzCatalog.objects.filter(pk=rz_id).select_related("profile").first()
        task_kind_id = matched_vk_id or kind_ids[0]
        if rz and not passport_matches_vehicle_rz(passport, rz, task_kind_id=task_kind_id):
            return (
                f"{label}: kontejner {num} je v pasportech evidován pod jiným druhem vozidla, "
                f"než odpovídá RZ {rz.value} z plánu svozů pro {vk_disp}. "
                f"Opravte pasport v Číselníky → Pasport kontejnerů, nebo zadejte jiné číslo kontejneru."
                f"{_CONTACT_DISPATCH_SUFFIX}"
            )

    in_use = _matrix_container_in_use_error(
        subject=subject,
        pair=pair,
        label=label,
        num=num,
        target_date=target_date,
    )
    if in_use:
        return in_use

    return None


def matrix_container_passport_errors_for_field(
    *,
    subject: NameSubjectProfile,
    pair: NameSubjectWasteSuffixPair,
    container_field_raw: str,
    target_date: date,
) -> list[str]:
    """Blokující chyby pasportu pro obsah textarea (každý neprázdný řádek = jeden požadavek)."""
    errors: list[str] = []
    for one_line in non_empty_container_entries(container_field_raw):
        err = matrix_container_passport_blocking_error(
            subject=subject,
            pair=pair,
            container_numbers=one_line,
            target_date=target_date,
        )
        if err:
            errors.append(err)
    return errors


__all__ = [
    "matrix_container_passport_blocking_error",
    "matrix_container_passport_errors_for_field",
    "matrix_unknown_passport_log_message",
    "matrix_unknown_passport_number",
    "matrix_unknown_passport_numbers_for_field",
]
