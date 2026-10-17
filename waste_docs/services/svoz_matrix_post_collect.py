"""Zpracování POST z matice požadavku na svoz — validace bez zápisu, bez blokace kvůli plánu."""

from __future__ import annotations

from dataclasses import dataclass

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair

from waste_docs.services.svoz_matrix_container_entries import non_empty_container_entries
from waste_docs.services.svoz_matrix_container_validation import (
    matrix_container_passport_blocking_error,
    matrix_unknown_passport_number,
)
from waste_docs.services.container_passport_ride_validation import normalize_container_number


@dataclass(frozen=True)
class SvozPendingLine:
    """Jeden řádek k vytvoření jako SvozTask po úspěšné validaci formuláře."""

    pair: NameSubjectWasteSuffixPair
    matrix_display_label: str
    yard_contact_note: str
    container_numbers: str
    claimed_unknown_container: str = ""


def _confirmed_unknown_numbers(post_data) -> set[str]:
    raw = (post_data.get("unknown_passport_confirmed") or "").strip()
    if not raw:
        return set()
    out: set[str] = set()
    for part in raw.replace(";", ",").split(","):
        n = normalize_container_number(part)
        if n:
            out.add(n)
    return out


def _confirmer_label(post_data) -> str:
    return (post_data.get("unknown_passport_confirmer") or "").strip()[:80]


def collect_pending_svoz_matrix_lines(
    posted_pks: list[str],
    post_data,
    subject: NameSubjectProfile,
    target_date,
):
    """
    Z POST složí seznam řádků k vytvoření + chyby (jen neplatný řádek / prázdný kontejner).

    Plán svozů se u odeslání neblokuje — úkoly bez slotu v plánu jdou na dashboard dispečera.
    Neznámý pasport vyžaduje potvrzení (unknown_passport_confirmed); pak jde řádek bez čísla.
    Vrací (pending_lines, validation_errors).
    """
    pending: list[SvozPendingLine] = []
    validation_errors: list[str] = []
    seen_containers: set[str] = set()
    confirmed_unknown = _confirmed_unknown_numbers(post_data)
    confirmer = _confirmer_label(post_data)

    for pk_raw in posted_pks:
        if not pk_raw.isdigit():
            continue
        pk = int(pk_raw)

        container_field = post_data.get(f"containers_{pk_raw}") or ""
        lines = non_empty_container_entries(container_field)
        if not lines:
            continue
        note_raw = (post_data.get(f"note_{pk_raw}") or "").strip()[:200]
        pair = (
            NameSubjectWasteSuffixPair.objects.filter(
                pk=pk,
                subject_profile=subject,
                yard_svoz_enabled=True,
            )
            .select_related("yard_vehicle_kind", "yard_svoz_activity", "waste_type")
            .prefetch_related("yard_vehicle_kinds")
            .first()
        )
        from catalogs.services.name_subject_pair_vehicle_kinds import pair_has_vehicle_kinds

        if not pair or not pair_has_vehicle_kinds(pair) or not pair.yard_svoz_activity_id:
            validation_errors.append(f"Neplatný řádek odpadu (pk {pk_raw}).")
            continue
        label_snap = (pair.yard_svoz_display_label or "").strip()
        for one_line in lines:
            container_key = normalize_container_number(one_line)
            if container_key:
                if container_key in seen_containers:
                    validation_errors.append(
                        f"{label_snap or 'Řádek matice'}: kontejner {container_key} je v tomto "
                        f"hlášení zadaný vícekrát (jen jeden požadavek na kontejner)."
                    )
                    continue
                seen_containers.add(container_key)
            passport_err = matrix_container_passport_blocking_error(
                subject=subject,
                pair=pair,
                container_numbers=one_line,
                target_date=target_date,
            )
            if passport_err:
                validation_errors.append(passport_err)
                continue

            unknown_num = matrix_unknown_passport_number(pair=pair, container_numbers=one_line)
            if unknown_num:
                if unknown_num not in confirmed_unknown:
                    validation_errors.append(
                        f"{label_snap or 'Řádek matice'}: kontejner {unknown_num} není v číselníku "
                        f"pasportů — potvrďte číslo v dialogu při odeslání, nebo ho opravte."
                    )
                    continue
                who = confirmer or "obsluha SD"
                audit = f"Potvrzeno: {unknown_num} ({who})"
                note = note_raw
                if note:
                    combined = f"{note} | {audit}"
                    note = combined[:200]
                else:
                    note = audit[:200]
                pending.append(
                    SvozPendingLine(
                        pair=pair,
                        matrix_display_label=label_snap,
                        yard_contact_note=note,
                        container_numbers="",
                        claimed_unknown_container=unknown_num,
                    )
                )
                continue

            pending.append(
                SvozPendingLine(
                    pair=pair,
                    matrix_display_label=label_snap,
                    yard_contact_note=note_raw,
                    container_numbers=one_line,
                )
            )

    return pending, validation_errors


__all__ = ["SvozPendingLine", "collect_pending_svoz_matrix_lines"]
