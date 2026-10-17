"""JSON snapshot subjektu F/P pro formulář průvodky (search, reload po uložení párů)."""

from __future__ import annotations

from django.db.models import Prefetch

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair
from catalogs.pair_ride_note.services.hint import enrich_pair_hint_with_ride_note
from catalogs.services.name_subject_pair_vehicle_kinds import pair_hint_vehicle_kind_client_fields
from catalogs.services.pair_fulfillment_address import fulfillment_address_value_for_pair
from catalogs.services.pair_fulfillment_address import central_fulfillment_address_value
from catalogs.services.phone import format_czech_contact_phone


def _pair_hints_from_pairs(
    pairs_all: list[NameSubjectWasteSuffixPair],
    profile: NameSubjectProfile,
) -> list[dict]:
    out = []
    for p in pairs_all:
        yard_kinds = list(p.yard_vehicle_kinds.all())
        kind_fields = pair_hint_vehicle_kind_client_fields(p)
        own_addr = ""
        if p.fulfillment_address_id and p.fulfillment_address:
            own_addr = (p.fulfillment_address.value or "").strip()
        hint = {
            "pair_id": p.pk,
            "waste_type_id": p.waste_type_id,
            "suffix_id": p.suffix_id,
            "contract_number": (p.contract_number or "").strip(),
            "fulfillment_address_value": fulfillment_address_value_for_pair(p, profile),
            "own_fulfillment_address_value": own_addr,
            "yard_vehicle_kind_id": p.yard_vehicle_kind_id,
            "yard_vehicle_kind_ids": kind_fields["yard_vehicle_kind_ids"],
            "covering_kind_ids": kind_fields["covering_kind_ids"],
            "vehicle_kind_constraint_hint": kind_fields["vehicle_kind_constraint_hint"],
            "yard_vehicle_kind_name": p.yard_vehicle_kind.name if p.yard_vehicle_kind_id else "",
            "yard_vehicle_kind_shortcut": p.yard_vehicle_kind.shortcut if p.yard_vehicle_kind_id else "",
            "yard_vehicle_kind_display": (
                ", ".join(k.display_label() for k in yard_kinds)
                or (p.yard_vehicle_kind.display_label() if p.yard_vehicle_kind_id else "")
            ),
            "activity_id": p.effective_yard_pruvodka_activity_id(),
        }
        out.append(enrich_pair_hint_with_ride_note(hint, p))
    return out


def subject_snapshot_for_pruvodka(profile: NameSubjectProfile) -> dict:
    """Jeden záznam ve stejném tvaru jako položka v subject_search."""
    if profile.is_collection_yard:
        from waste_docs.yard_matrix import yard_new_date_matrix_ready_qs

        pairs_all = list(
            yard_new_date_matrix_ready_qs(profile)
            .select_related(
                "waste_type",
                "yard_vehicle_kind",
                "fulfillment_address",
                "yard_svoz_activity",
                "yard_pruvodka_activity",
            )
            .prefetch_related("yard_vehicle_kinds")
        )
        allowed_waste_ids = list(dict.fromkeys(p.waste_type_id for p in pairs_all))
    else:
        pairs_all = list(profile.waste_suffix_pairs.all())
        pair_waste_ids = list(dict.fromkeys(p.waste_type_id for p in pairs_all))
        allowed_waste_ids = (
            pair_waste_ids
            if pair_waste_ids
            else list(profile.allowed_waste_types.values_list("id", flat=True))
        )
    return {
        "subject_profile_id": profile.pk,
        "ico": profile.ico.value if profile.ico_id else "",
        "name_value": profile.name.value if profile.name_id else "",
        "name_id": profile.name_id,
        "ico_id": profile.ico_id,
        "address_id": profile.fulfillment_address_id or profile.facility_address_id,
        "facility_address_value": profile.facility_address.value if profile.facility_address_id else "",
        "fulfillment_address_value": central_fulfillment_address_value(profile),
        "fulfillment_latitude": (
            str(profile.fulfillment_latitude) if profile.fulfillment_latitude is not None else ""
        ),
        "fulfillment_longitude": (
            str(profile.fulfillment_longitude) if profile.fulfillment_longitude is not None else ""
        ),
        "contact_phone": format_czech_contact_phone(profile.contact_phone)
        if (profile.contact_phone or "").strip()
        else "",
        "contact_note": profile.contact_note or "",
        "allowed_waste_type_ids": allowed_waste_ids,
        "default_waste_type_id": allowed_waste_ids[0] if allowed_waste_ids else "",
        "pair_hints": _pair_hints_from_pairs(pairs_all, profile),
        "label": profile.name.value if profile.name_id else profile.company_name,
    }


def profile_queryset_for_pruvodka_snapshot():
    pair_qs = NameSubjectWasteSuffixPair.objects.select_related(
        "waste_type",
        "yard_vehicle_kind",
        "fulfillment_address",
        "yard_svoz_activity",
        "yard_pruvodka_activity",
    ).prefetch_related("yard_vehicle_kinds")
    return NameSubjectProfile.objects.select_related(
        "name",
        "ico",
        "address_profile__facility_address",
        "address_profile__fulfillment_address",
    ).prefetch_related(
        Prefetch("waste_suffix_pairs", queryset=pair_qs),
        "allowed_waste_types",
    )


def get_profile_for_pruvodka_snapshot(pk: int) -> NameSubjectProfile:
    return profile_queryset_for_pruvodka_snapshot().get(pk=pk)
