"""Předvyplnění navazující průvodky (2. část) z rodičovského záznamu — bez kopírování data jízdy."""

from __future__ import annotations

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair
from catalogs.services.pair_fulfillment_address import central_fulfillment_address_value
from catalogs.waste_catalog_code import normalize_waste_catalog_code
from waste_docs.models import Pruvodka
from waste_docs.services.customer_request_prefill import _fulfillment_address_options


def _facility_value(parent: Pruvodka) -> str:
    if not parent.name_id:
        return ""
    prof = (
        NameSubjectProfile.objects.filter(name_id=parent.name_id)
        .select_related("address_profile__facility_address")
        .first()
    )
    if prof and prof.facility_address_id:
        return prof.facility_address.value
    return ""


def _central_fulfillment_value(item: Pruvodka) -> str:
    if not item.name_id:
        return ""
    prof = (
        NameSubjectProfile.objects.filter(name_id=item.name_id)
        .select_related("address_profile__fulfillment_address")
        .first()
    )
    if not prof:
        return ""
    return central_fulfillment_address_value(prof)


def _fulfillment_value_for_item(item: Pruvodka) -> str:
    """Adresa plnění jízdy; když chybí, centrální plnění — nikdy provozovna."""
    if item.address_id and item.address:
        val = (item.address.value or "").strip()
        if val:
            return val
    return _central_fulfillment_value(item)


def _fulfillment_address_options_for_ride(item: Pruvodka) -> list[dict]:
    """Uložená adresa jízdy + vlastní adresy párů F/P u odpadu (pro combobox)."""
    fulfillment = _fulfillment_value_for_item(item)
    if not item.name_id or not item.waste_type_id:
        if fulfillment:
            return [
                {
                    "value": fulfillment,
                    "label": fulfillment,
                    "title": fulfillment,
                }
            ]
        return []

    sub = (
        NameSubjectProfile.objects.filter(name_id=item.name_id)
        .select_related("address_profile__fulfillment_address")
        .first()
    )
    pairs: list[NameSubjectWasteSuffixPair] = []
    if sub:
        qs = NameSubjectWasteSuffixPair.objects.filter(
            subject_profile=sub,
            waste_type_id=item.waste_type_id,
        )
        if item.suffix_id:
            qs = qs.filter(suffix_id=item.suffix_id)
        pairs = list(
            qs.select_related("fulfillment_address", "yard_vehicle_kind")
            .prefetch_related("yard_vehicle_kinds")
            .order_by("sort_order", "id")
        )
        # Pokud filtr koncovky nic nedá, nabídni všechny páry odpadu (stejně jako JS kandidáti).
        if item.suffix_id and not pairs:
            pairs = list(
                NameSubjectWasteSuffixPair.objects.filter(
                    subject_profile=sub,
                    waste_type_id=item.waste_type_id,
                )
                .select_related("fulfillment_address", "yard_vehicle_kind")
                .prefetch_related("yard_vehicle_kinds")
                .order_by("sort_order", "id")
            )

    return _fulfillment_address_options(
        default_address=fulfillment,
        cr_address=fulfillment,
        subject=sub,
        pairs=pairs,
    )


def build_follow_up_prefill(parent: Pruvodka) -> dict:
    """
    Vrací {'initial': {...}, 'client': {...}}.
    initial — doplněk do PruvodkaForm.initial (activity, follow_up_parent, drive_date neřeší).
    client — waste_docs JSON pro synchronizaci comboboxů v prohlížeči.
    """
    initial: dict = {}
    if not parent:
        return {"initial": initial, "client": None}

    if parent.ico_id:
        initial["ico"] = parent.ico_id
    if parent.name_id:
        initial["name"] = parent.name_id
    if parent.waste_type_id:
        initial["waste_type"] = parent.waste_type_id
    if parent.suffix_id:
        initial["suffix"] = parent.suffix_id
    if parent.vehicle_rz_id:
        initial["vehicle_rz"] = parent.vehicle_rz_id
    if parent.container_passport_id:
        initial["container_passport"] = parent.container_passport_id
    if parent.contact_phone:
        initial["contact_phone"] = parent.contact_phone
    if parent.contract_number:
        initial["contract_number"] = parent.contract_number
    fulfillment = _fulfillment_value_for_item(parent)
    if fulfillment:
        initial["fulfillment_address_value"] = fulfillment
    if parent.name_snapshot:
        initial["ico_lookup"] = parent.name_snapshot.strip()
    if parent.waste_type_id and parent.waste_type:
        wt = parent.waste_type
        initial["waste_code_display"] = normalize_waste_catalog_code(wt.code) or (wt.code or "")
        initial["waste_category_display"] = wt.category or ""
    fac = _facility_value(parent)
    if fac:
        initial["facility_address_display"] = fac

    q = (parent.name_snapshot or "").strip()
    fulfillment_options = _fulfillment_address_options_for_ride(parent)

    client = {
        "ico_id": parent.ico_id,
        "name_id": parent.name_id,
        "ico_lookup": initial.get("ico_lookup", ""),
        "subject_search_query": q[:120] if q else "",
        "fulfillment_address": fulfillment,
        "fulfillment_address_options": fulfillment_options,
        "facility_address": fac,
        "contract_number": parent.contract_number or "",
        "contact_phone": parent.contact_phone or "",
        "waste_type_id": parent.waste_type_id,
        "suffix_id": parent.suffix_id,
        "vehicle_rz_id": parent.vehicle_rz_id,
        "container_passport_id": parent.container_passport_id,
    }
    return {"initial": initial, "client": client}


def build_edit_form_prefill_bundle(item: Pruvodka) -> dict:
    """
    Předvyplnění formuláře úpravy průvodky — stejná data jako v DB (subjekt, adresy, odpad, RZ, řidič…).
    client se po načtení stránky aplikuje v JS po pravidlech činnosti.
    """
    b = build_follow_up_prefill(item)
    initial = dict(b["initial"])
    client = dict(b["client"]) if b["client"] else {}
    client["driver_id"] = item.driver_id
    client["container_number"] = item.container_number or ""
    client["container_number_2"] = item.container_number_2 or ""
    client["container_passport_id"] = item.container_passport_id
    initial["container_number"] = item.container_number or ""
    initial["container_number_2"] = item.container_number_2 or ""
    if item.container_passport_id:
        initial["container_passport"] = item.container_passport_id
    note = (item.contact_note or "").strip()
    if note:
        initial["contact_note"] = note
        client["contact_note"] = note
    return {"initial": initial, "client": client}
