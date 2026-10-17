"""Předvyplnění formuláře průvodky z otevřeného požadavku na nebezpečný odpad."""

from __future__ import annotations

from catalogs.models import NameSubjectWasteSuffixPair
from catalogs.services.pair_fulfillment_address import fulfillment_address_for_pruvodka_context
from catalogs.waste_catalog_code import normalize_waste_catalog_code
from waste_docs.models import YardHazardousWasteRequest
from waste_docs.svoz_prefill import _split_container_numbers


def build_yard_hazard_request_prefill_bundle(request_obj: YardHazardousWasteRequest) -> dict:
    item = (
        YardHazardousWasteRequest.objects.filter(pk=request_obj.pk)
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
    if not item:
        return {"initial": {}, "client": None}

    sub = item.subject_profile
    pair = item.source_waste_suffix_pair
    if pair is None:
        pair = (
            NameSubjectWasteSuffixPair.objects.filter(
                subject_profile=sub,
                waste_type_id=item.waste_type_id,
                suffix_id=item.suffix_id,
            )
            .select_related("fulfillment_address")
            .first()
        )
    contract = (pair.contract_number or "").strip() if pair else ""

    fulfillment_val = fulfillment_address_for_pruvodka_context(
        subject_profile=sub,
        waste_type_id=item.waste_type_id,
        suffix_id=item.suffix_id,
        preferred_pair_id=pair.pk if pair else None,
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

    wt = item.waste_type
    code_disp = ""
    cat_disp = ""
    if wt:
        code_disp = normalize_waste_catalog_code(wt.code) or (wt.code or "")
        cat_disp = (wt.category or "").strip()

    c1, c2, note_extra = _split_container_numbers(item.container_numbers)
    yard_note = (item.yard_contact_note or "").strip()
    note_parts = [p for p in (yard_note, note_extra) if p]
    combined_note = " ".join(note_parts).strip()[:200]

    initial: dict = {}
    if sub.ico_id:
        initial["ico"] = sub.ico_id
    if sub.name_id:
        initial["name"] = sub.name_id
    if item.waste_type_id:
        initial["waste_type"] = item.waste_type_id
    if item.suffix_id:
        initial["suffix"] = item.suffix_id
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
    if item.activity_id:
        initial["activity"] = item.activity_id

    client = {
        "ico_id": sub.ico_id,
        "name_id": sub.name_id,
        "ico_lookup": ico_lookup,
        "subject_search_query": q[:120] if q else "",
        "fulfillment_address": fulfillment_val,
        "facility_address": fac_val,
        "contract_number": contract,
        "contact_phone": phone,
        "waste_type_id": item.waste_type_id,
        "suffix_id": item.suffix_id,
        "vehicle_rz_id": None,
        "container_number": c1,
        "container_number_2": c2,
        "contact_note": combined_note,
        "required_vehicle_kind_id": item.vehicle_kind_id,
        "activity_id": item.activity_id,
    }
    return {"initial": initial, "client": client}
