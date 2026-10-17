"""Přiřazení činnosti z matice sběrného dvora podle POST dat formuláře průvodky."""

from __future__ import annotations

from typing import Any

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair
from catalogs.services.name_subject_pair_vehicle_kinds import pair_hint_vehicle_kind_client_fields
from catalogs.services.pair_fulfillment_address import fulfillment_address_value_for_pair
from users.services.sberny_dvur import get_sberny_dvur_subject, is_sberny_dvur_role
from waste_docs.yard_matrix import yard_new_date_matrix_ready_qs


def yard_standalone_pair_hints_payload(
    subject: NameSubjectProfile,
    pairs: list[NameSubjectWasteSuffixPair],
) -> list[dict]:
    """Řádky matice pro JS klienta průvodky ze sběrného dvora (včetně adresy plnění)."""
    out: list[dict] = []
    for pair in pairs:
        activity_id = pair.effective_yard_pruvodka_activity_id()
        if not activity_id:
            continue
        kind_fields = pair_hint_vehicle_kind_client_fields(pair)
        out.append(
            {
                "waste_type_id": pair.waste_type_id,
                "suffix_id": pair.suffix_id,
                "contract_number": (pair.contract_number or "").strip(),
                "activity_id": activity_id,
                "vehicle_kind_id": pair.yard_vehicle_kind_id,
                "yard_vehicle_kind_id": pair.yard_vehicle_kind_id,
                "yard_vehicle_kind_ids": kind_fields["yard_vehicle_kind_ids"],
                "covering_kind_ids": kind_fields["covering_kind_ids"],
                "vehicle_kind_constraint_hint": kind_fields["vehicle_kind_constraint_hint"],
                "fulfillment_address_value": fulfillment_address_value_for_pair(pair, subject),
            }
        )
    return out


def yard_standalone_activity_id_from_form_data(user: Any, data: Any) -> str | None:
    """
    V režimu samostatné průvodky ze dvora vrátí ID činnosti z řádku matice (waste_type + suffix),
    jinak None.
    """
    if not user or not data:
        return None
    if not is_sberny_dvur_role(user):
        return None
    ys = get_sberny_dvur_subject(user)
    if not ys:
        return None
    wt_raw = (data.get("waste_type") or "").strip()
    suf_raw = (data.get("suffix") or "").strip()
    if not wt_raw.isdigit() or not suf_raw.isdigit():
        return None
    pair = (
        yard_new_date_matrix_ready_qs(ys)
        .filter(
            waste_type_id=int(wt_raw),
            suffix_id=int(suf_raw),
        )
        .first()
    )
    if not pair:
        return None
    eff = pair.effective_yard_pruvodka_activity_id()
    return str(eff) if eff else None
