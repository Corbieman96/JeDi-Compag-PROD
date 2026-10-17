"""Adresa plnění z řádku F/P s fallbackem na centrální adresu subjektu."""

from __future__ import annotations

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair
from catalogs.services.fulfillment_address import normalize_fulfillment_address
from catalogs.services.name_subject_pair_vehicle_kinds import pair_for_pruvodka_context


def central_fulfillment_address_value(profile: NameSubjectProfile) -> str:
    """Centrální Adresa plnění subjektu — bez fallbacku na provozovnu."""
    if profile.fulfillment_address_id and profile.fulfillment_address:
        return (profile.fulfillment_address.value or "").strip()
    return ""


def _fulfillment_address_from_form(form) -> str:
    if form is None:
        return ""
    if getattr(form, "is_bound", False):
        return (form.data.get("fulfillment_address_value") or "").strip()
    field = form.fields.get("fulfillment_address_value") if hasattr(form, "fields") else None
    if field is not None and field.initial not in (None, ""):
        return (field.initial or "").strip()
    return ""


def resolved_central_fulfillment_address(
    *,
    form=None,
    profile: NameSubjectProfile | None = None,
) -> str:
    """Aktuální adresa plnění — z formuláře (POST/initial) nebo z uloženého profilu."""
    raw = _fulfillment_address_from_form(form)
    if raw:
        return normalize_fulfillment_address(raw)
    if profile:
        return central_fulfillment_address_value(profile)
    return ""


def known_fulfillment_addresses_for_form(
    *,
    form=None,
    profile: NameSubjectProfile | None = None,
) -> list[str]:
    """Známé adresy plnění; první položka = aktuální adresa z formuláře nebo profilu."""
    base = known_fulfillment_addresses_for_subject(profile) if profile else []
    central = resolved_central_fulfillment_address(form=form, profile=profile)
    if not central:
        return base
    seen: set[str] = {central}
    out: list[str] = [central]
    for addr in base:
        if addr not in seen:
            seen.add(addr)
            out.append(addr)
    return out


def fulfillment_address_value_for_pair(
    pair: NameSubjectWasteSuffixPair | None,
    profile: NameSubjectProfile | None,
) -> str:
    if pair and pair.fulfillment_address_id and pair.fulfillment_address:
        return (pair.fulfillment_address.value or "").strip()
    if profile:
        return central_fulfillment_address_value(profile)
    return ""


def known_fulfillment_addresses_for_subject(profile: NameSubjectProfile | None) -> list[str]:
    """Všechny známé adresy plnění subjektu — centrální + uložené na řádcích F/P."""
    if not profile:
        return []
    seen: set[str] = set()
    out: list[str] = []
    central = central_fulfillment_address_value(profile)
    if central:
        seen.add(central)
        out.append(central)
    pairs_qs = profile.waste_suffix_pairs.exclude(fulfillment_address__isnull=True).select_related(
        "fulfillment_address"
    )
    for pair in pairs_qs:
        if not pair.fulfillment_address_id or not pair.fulfillment_address:
            continue
        val = (pair.fulfillment_address.value or "").strip()
        if not val or val in seen:
            continue
        seen.add(val)
        out.append(val)
    return out


def fulfillment_address_for_pruvodka_context(
    *,
    subject_profile: NameSubjectProfile | None = None,
    waste_type_id: int | None = None,
    suffix_id: int | None = None,
    vehicle_rz=None,
    container_passport=None,
    preferred_pair_id: int | None = None,
    pair: NameSubjectWasteSuffixPair | None = None,
) -> str:
    if pair is None and subject_profile is not None:
        pair = pair_for_pruvodka_context(
            subject_profile=subject_profile,
            waste_type_id=waste_type_id,
            suffix_id=suffix_id,
            vehicle_rz=vehicle_rz,
            container_passport=container_passport,
            preferred_pair_id=preferred_pair_id,
        )
    return fulfillment_address_value_for_pair(pair, subject_profile)
