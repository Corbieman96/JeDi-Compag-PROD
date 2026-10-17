"""Načtení ride_note páru subjekt×odpad×adresa (ne z pair_hints v prohlížeči)."""

from __future__ import annotations

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair
from catalogs.pair_ride_note.services.hint import pair_ride_note_hint_value
from catalogs.services.pair_fulfillment_address import fulfillment_address_value_for_pair


def _addr_key(value: str) -> str:
    return " ".join((value or "").split())


def _pair_matches_address(
    pair: NameSubjectWasteSuffixPair,
    profile: NameSubjectProfile,
    wanted: str,
) -> bool:
    own = ""
    if pair.fulfillment_address_id and pair.fulfillment_address:
        own = _addr_key(pair.fulfillment_address.value or "")
    resolved = _addr_key(fulfillment_address_value_for_pair(pair, profile))
    return bool(wanted) and (own == wanted or resolved == wanted)


def _note_from_pairs(
    pairs: list[NameSubjectWasteSuffixPair],
    *,
    profile: NameSubjectProfile,
    address: str,
) -> str:
    wanted = _addr_key(address)
    if wanted:
        matched = [p for p in pairs if _pair_matches_address(p, profile, wanted)]
        if not matched:
            return ""
        with_note = [p for p in matched if pair_ride_note_hint_value(p)]
        chosen = with_note[0] if with_note else matched[0]
        return pair_ride_note_hint_value(chosen)
    return ""


def lookup_pair_ride_note(
    *,
    pair_id: int | None = None,
    name_id: int | None = None,
    waste_type_id: int | None = None,
    suffix_id: int | None = None,
    address: str = "",
) -> str:
    """Text Poznámky do jízdy z DB. Primárně pair_id; jinak name+odpad+adresa."""
    if pair_id:
        pair = (
            NameSubjectWasteSuffixPair.objects.filter(pk=pair_id)
            .select_related(
                "fulfillment_address",
                "subject_profile",
                "subject_profile__address_profile__fulfillment_address",
            )
            .first()
        )
        if pair:
            if name_id and pair.subject_profile and pair.subject_profile.name_id != name_id:
                pair = None
            else:
                note = pair_ride_note_hint_value(pair)
                if note:
                    return note
                if not _addr_key(address):
                    return ""

    if not name_id or not waste_type_id:
        return ""

    profile = (
        NameSubjectProfile.objects.filter(name_id=name_id)
        .select_related("address_profile__fulfillment_address")
        .first()
    )
    if not profile:
        return ""

    qs = NameSubjectWasteSuffixPair.objects.filter(
        subject_profile=profile,
        waste_type_id=waste_type_id,
    ).select_related("fulfillment_address")
    if suffix_id:
        qs = qs.filter(suffix_id=suffix_id)
    pairs = list(qs.order_by("sort_order", "id"))
    return _note_from_pairs(pairs, profile=profile, address=address)
