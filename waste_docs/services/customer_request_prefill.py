"""Předvyplnění formuláře průvodky z CustomerRequest připraveného pro dispatch."""

from __future__ import annotations

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair
from catalogs.services.name_subject_pair_vehicle_kinds import (
    pair_hint_vehicle_kind_client_fields,
    pair_vehicle_kind_constraint_hint,
    pair_vehicle_kind_ids,
    pair_vehicle_kinds_display,
)
from catalogs.services.pair_fulfillment_address import (
    central_fulfillment_address_value,
    fulfillment_address_for_pruvodka_context,
)
from catalogs.waste_catalog_code import normalize_waste_catalog_code
from customer_requests.models import CustomerRequest
from catalogs.pair_ride_note.services.hint import pair_ride_note_hint_value
from waste_docs.services.customer_request_ride_note import ride_note_for_customer_request
from waste_docs.services.customer_request_vehicle_kind import (
    effective_vehicle_kind_id,
    effective_vehicle_kind_label,
)


def _pick_pair_for_customer_request(
    pairs: list[NameSubjectWasteSuffixPair],
    *,
    vehicle_kind_id: int | None,
) -> NameSubjectWasteSuffixPair | None:
    if not pairs:
        return None
    if vehicle_kind_id:
        vid = int(vehicle_kind_id)
        for pair in pairs:
            if vid in pair_vehicle_kind_ids(pair):
                return pair
    return pairs[0]


def _own_fulfillment_address_value(pair: NameSubjectWasteSuffixPair | None) -> str:
    if not pair or not pair.fulfillment_address_id or not pair.fulfillment_address:
        return ""
    return (pair.fulfillment_address.value or "").strip()


def _pick_last_pair_with_own_address(
    pairs: list[NameSubjectWasteSuffixPair],
    *,
    vehicle_kind_id: int | None,
) -> NameSubjectWasteSuffixPair | None:
    """Poslední řádek s vlastní adresou plnění (sort_order, id); nejdřív shoda druhu vozidla."""
    with_own = [pair for pair in pairs if _own_fulfillment_address_value(pair)]
    if not with_own:
        return None
    if vehicle_kind_id:
        vid = int(vehicle_kind_id)
        vk_own = [pair for pair in with_own if vid in pair_vehicle_kind_ids(pair)]
        if vk_own:
            return vk_own[-1]
    return with_own[-1]


def _fulfillment_address_options(
    *,
    default_address: str,
    cr_address: str,
    subject: NameSubjectProfile | None,
    pairs: list[NameSubjectWasteSuffixPair],
) -> list[dict]:
    """Unikátní adresy: default (poslední pár), adresa požadavku, vlastní z párů, centrální."""
    seen: set[str] = set()
    options: list[dict] = []

    def add(value: str, label: str | None = None) -> None:
        text = (value or "").strip()
        if not text or text in seen:
            return
        seen.add(text)
        options.append(
            {
                "value": text,
                "label": (label or text).strip() or text,
                "title": text,
            }
        )

    if default_address:
        add(default_address)
    if cr_address:
        add(cr_address)

    for pair in pairs:
        if not pair.fulfillment_address_id or not pair.fulfillment_address:
            continue
        addr = (pair.fulfillment_address.value or "").strip()
        if not addr:
            continue
        kinds = pair_vehicle_kinds_display(pair)
        label = f"{kinds} — {addr}" if kinds else addr
        add(addr, label)

    if subject:
        central = central_fulfillment_address_value(subject)
        if central:
            add(central)

    return options


def build_customer_request_prefill_bundle(cr: CustomerRequest) -> dict:
    """initial pro PruvodkaForm + client pro formulář průvodky (stejný tvar jako svozPrefill)."""
    cr_full = (
        CustomerRequest.objects.filter(pk=cr.pk)
        .select_related("name", "activity", "vehicle_kind", "waste_type", "suffix", "address")
        .prefetch_related("activity__vehicle_kinds")
        .first()
    )
    if not cr_full:
        return {"initial": {}, "client": None}

    sub = (
        NameSubjectProfile.objects.filter(name_id=cr_full.name_id)
        .select_related(
            "ico",
            "name",
            "address_profile__fulfillment_address",
            "address_profile__facility_address",
        )
        .first()
    )

    pairs: list[NameSubjectWasteSuffixPair] = []
    pair = None
    pair_kind_fields: dict = {}
    req_vk_id = effective_vehicle_kind_id(cr_full)
    if sub and cr_full.waste_type_id:
        qs = NameSubjectWasteSuffixPair.objects.filter(
            subject_profile=sub,
            waste_type_id=cr_full.waste_type_id,
        )
        if cr_full.suffix_id:
            qs = qs.filter(suffix_id=cr_full.suffix_id)
        pairs = list(
            qs.select_related("fulfillment_address", "yard_vehicle_kind")
            .prefetch_related("yard_vehicle_kinds")
            .order_by("sort_order", "id")
        )
        pair = _pick_pair_for_customer_request(pairs, vehicle_kind_id=req_vk_id)
        if pair:
            pair_kind_fields = pair_hint_vehicle_kind_client_fields(pair)
    contract = (cr_full.contract_number or "").strip() or (
        (pair.contract_number or "").strip() if pair else ""
    )

    cr_address_val = ""
    if cr_full.address_id and cr_full.address:
        cr_address_val = (cr_full.address.value or "").strip()

    fulfillment_val = ""
    addr_pair = _pick_last_pair_with_own_address(pairs, vehicle_kind_id=req_vk_id)
    if addr_pair:
        fulfillment_val = _own_fulfillment_address_value(addr_pair)
    if not fulfillment_val:
        fulfillment_val = cr_address_val
    if sub and not fulfillment_val:
        fulfillment_val = fulfillment_address_for_pruvodka_context(
            subject_profile=sub,
            waste_type_id=cr_full.waste_type_id,
            suffix_id=cr_full.suffix_id,
            pair=pair,
        )

    fulfillment_options = _fulfillment_address_options(
        default_address=fulfillment_val,
        cr_address=cr_address_val,
        subject=sub,
        pairs=pairs,
    )

    fac_val = (cr_full.facility_address_snapshot or "").strip()
    if not fac_val and sub and sub.facility_address_id and sub.facility_address:
        fac_val = (sub.facility_address.value or "").strip()

    ico_id = sub.ico_id if sub else None
    name_id = cr_full.name_id

    parts = []
    if sub and sub.ico and sub.ico.value:
        parts.append(sub.ico.value.strip())
    if sub and sub.name and sub.name.value:
        parts.append(sub.name.value.strip())
    elif cr_full.name and cr_full.name.value:
        parts.append(cr_full.name.value.strip())
    ico_lookup = " ".join(parts) if parts else ((sub.company_name or "").strip() if sub else "")

    q = (sub.ico.value if sub and sub.ico_id else "") or ""
    q = (q or "").strip()
    if len(q) < 2 and sub and sub.name_id:
        q = (sub.name.value if sub.name else "") or ""
    q = (q or "").strip()
    if len(q) < 2:
        q = ico_lookup[:120]

    wt = cr_full.waste_type
    code_disp = ""
    cat_disp = ""
    if wt:
        code_disp = normalize_waste_catalog_code(wt.code) or (wt.code or "")
        cat_disp = (wt.category or "").strip()

    phone = (cr_full.contact_phone or "").strip()
    if not phone and sub:
        phone = (sub.contact_phone or "").strip()
    note = ride_note_for_customer_request(cr_full)
    if not note and pair:
        note = pair_ride_note_hint_value(pair)

    initial: dict = {"drive_date": cr_full.target_date}
    if ico_id:
        initial["ico"] = ico_id
    if name_id:
        initial["name"] = name_id
    if cr_full.waste_type_id:
        initial["waste_type"] = cr_full.waste_type_id
    if cr_full.suffix_id:
        initial["suffix"] = cr_full.suffix_id
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
    if phone:
        initial["contact_phone"] = phone
    if contract:
        initial["contract_number"] = contract
    if note:
        initial["contact_note"] = note
    if cr_full.activity_id:
        initial["activity"] = cr_full.activity_id

    covering_ids = pair_kind_fields.get("covering_kind_ids") or []
    if not covering_ids and req_vk_id:
        from catalogs.services.vehicle_kind_compatibility import vehicle_kinds_covering_task

        covering_ids = sorted(vehicle_kinds_covering_task(int(req_vk_id)))

    client = {
        "ico_id": ico_id,
        "name_id": name_id,
        "ico_lookup": ico_lookup,
        "subject_search_query": q[:120] if q else "",
        "fulfillment_address": fulfillment_val,
        "fulfillment_address_options": fulfillment_options,
        "facility_address": fac_val,
        "contract_number": contract,
        "contact_phone": phone,
        "waste_type_id": cr_full.waste_type_id,
        "suffix_id": cr_full.suffix_id,
        "vehicle_rz_id": None,
        "driver_id": None,
        "container_number": "",
        "container_number_2": "",
        "contact_note": note,
        "required_vehicle_kind_id": req_vk_id,
        "covering_kind_ids": covering_ids,
        "vehicle_kind_constraint_hint": pair_kind_fields.get("vehicle_kind_constraint_hint")
        or (pair_vehicle_kind_constraint_hint(pair) if pair else ""),
        "vehicle_kind_label": effective_vehicle_kind_label(cr_full),
        "activity_id": cr_full.activity_id,
        "skip_driver_rz_auto_select": True,
    }
    return {"initial": initial, "client": client}
