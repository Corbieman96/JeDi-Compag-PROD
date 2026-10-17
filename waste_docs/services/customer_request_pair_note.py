"""Poznámka z páru odpad+koncovka pro CustomerRequest (stejný text jako do jízdy)."""

from __future__ import annotations

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair
from catalogs.pair_ride_note.services.hint import pair_ride_note_hint_value
from catalogs.services.name_subject_pair_vehicle_kinds import pair_vehicle_kind_ids
from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_vehicle_kind import effective_vehicle_kind_id


def _pick_pair(
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


def pair_for_customer_request(cr: CustomerRequest) -> NameSubjectWasteSuffixPair | None:
    """Pár subjektu podle odpadu/koncovky (+ druh vozidla), stejný výběr jako prefill."""
    if not cr.name_id or not cr.waste_type_id:
        return None
    sub = NameSubjectProfile.objects.filter(name_id=cr.name_id).first()
    if not sub:
        return None
    qs = NameSubjectWasteSuffixPair.objects.filter(
        subject_profile=sub,
        waste_type_id=cr.waste_type_id,
    )
    if cr.suffix_id:
        qs = qs.filter(suffix_id=cr.suffix_id)
    pairs = list(
        qs.select_related("fulfillment_address", "yard_vehicle_kind")
        .prefetch_related("yard_vehicle_kinds")
        .order_by("sort_order", "id")
    )
    return _pick_pair(pairs, vehicle_kind_id=effective_vehicle_kind_id(cr))


def pair_ride_note_for_customer_request(cr: CustomerRequest) -> str:
    """ride_note páru, jinak yard_dispatch_note_text; prázdné když pár/poznámka chybí."""
    return pair_ride_note_hint_value(pair_for_customer_request(cr))


__all__ = [
    "pair_for_customer_request",
    "pair_ride_note_for_customer_request",
]
