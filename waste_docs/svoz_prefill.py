"""Předvyplnění formuláře průvodky z otevřeného SvozTask."""

from __future__ import annotations

from catalogs.models import NameSubjectWasteSuffixPair
from catalogs.services.pair_fulfillment_address import fulfillment_address_for_pruvodka_context
from catalogs.services.vehicle_kind_compatibility import vehicle_kinds_covering_task
from catalogs.waste_catalog_code import normalize_waste_catalog_code
from waste_docs.models import SvozTask


def _split_container_numbers(raw: str) -> tuple[str, str, str]:
    text = (raw or "").replace(";", ",")
    parts = [p.strip() for p in text.split(",") if p.strip()]
    c1 = parts[0] if parts else ""
    c2 = parts[1] if len(parts) > 1 else ""
    extra = parts[2:] if len(parts) > 2 else []
    note = ("Další kontejnery: " + ", ".join(extra)) if extra else ""
    return c1, c2, note


def build_svoz_task_prefill_bundle(task: SvozTask) -> dict:
    """initial pro PruvodkaForm + client pro formulář průvodky (js/pruvodka; stejný tvar jako followUpPrefill)."""
    task_full = (
        SvozTask.objects.filter(pk=task.pk)
        .select_related(
            "subject_profile",
            "subject_profile__name",
            "subject_profile__ico",
            "subject_profile__address_profile__fulfillment_address",
            "subject_profile__address_profile__facility_address",
            "waste_type",
            "suffix",
            "vehicle_kind",
            "activity",
        )
        .first()
    )
    if not task_full:
        return {"initial": {}, "client": None}
    sub = task_full.subject_profile
    pair = (
        NameSubjectWasteSuffixPair.objects.filter(
            subject_profile=sub,
            waste_type_id=task_full.waste_type_id,
            suffix_id=task_full.suffix_id,
        )
        .select_related("fulfillment_address")
        .first()
    )
    contract = (pair.contract_number or "").strip() if pair else ""

    fulfillment_val = fulfillment_address_for_pruvodka_context(
        subject_profile=sub,
        waste_type_id=task_full.waste_type_id,
        suffix_id=task_full.suffix_id,
        preferred_pair_id=getattr(task_full, "source_waste_suffix_pair_id", None),
        pair=pair,
    )

    fac_val = ""
    if sub.facility_address_id and sub.facility_address:
        fac_val = sub.facility_address.value

    parts = []
    if sub.ico and sub.ico.value:
        parts.append(sub.ico.value.strip())
    if sub.name and sub.name.value:
        parts.append(sub.name.value.strip())
    ico_lookup = " ".join(parts) if parts else (sub.company_name or "").strip()

    q = (sub.ico.value if sub.ico_id else "") or ""
    q = (q or "").strip()
    if len(q) < 2:
        q = (sub.name.value if sub.name_id else "") or ""
    q = (q or "").strip()
    if len(q) < 2:
        q = ico_lookup[:120]

    wt = task_full.waste_type
    code_disp = ""
    cat_disp = ""
    if wt:
        code_disp = normalize_waste_catalog_code(wt.code) or (wt.code or "")
        cat_disp = (wt.category or "").strip()

    c1, c2, note_extra = _split_container_numbers(task_full.container_numbers)
    yard_note = (task_full.yard_contact_note or "").strip()
    note_parts = [p for p in (yard_note, note_extra) if p]
    combined_note = " ".join(note_parts).strip()[:200]

    initial: dict = {}
    if sub.ico_id:
        initial["ico"] = sub.ico_id
    if sub.name_id:
        initial["name"] = sub.name_id
    if task_full.waste_type_id:
        initial["waste_type"] = task_full.waste_type_id
    if task_full.suffix_id:
        initial["suffix"] = task_full.suffix_id
    if fulfillment_val:
        initial["fulfillment_address_value"] = fulfillment_val
    if ico_lookup:
        initial["ico_lookup"] = ico_lookup
    if fac_val:
        initial["facility_address_display"] = fac_val
    if code_disp:
        initial["waste_code_display"] = code_disp
    if cat_disp:
        initial["waste_category_display"] = cat_disp
    if c1:
        initial["container_number"] = c1
    if c2:
        initial["container_number_2"] = c2
    phone = (sub.contact_phone or "").strip()
    if phone:
        initial["contact_phone"] = phone
    if contract:
        initial["contract_number"] = contract
    if combined_note:
        initial["contact_note"] = combined_note
    if task_full.activity_id:
        initial["activity"] = task_full.activity_id

    client = {
        "ico_id": sub.ico_id,
        "name_id": sub.name_id,
        "ico_lookup": ico_lookup,
        "subject_search_query": q[:120] if q else "",
        "fulfillment_address": fulfillment_val,
        "facility_address": fac_val,
        "contract_number": contract,
        "contact_phone": phone,
        "waste_type_id": task_full.waste_type_id,
        "suffix_id": task_full.suffix_id,
        "vehicle_rz_id": None,
        "container_number": c1,
        "container_number_2": c2,
        "contact_note": combined_note,
        "required_vehicle_kind_id": task_full.vehicle_kind_id,
        "covering_kind_ids": (
            sorted(vehicle_kinds_covering_task(int(task_full.vehicle_kind_id)))
            if task_full.vehicle_kind_id
            else []
        ),
        "activity_id": task_full.activity_id,
    }
    return {"initial": initial, "client": client}
