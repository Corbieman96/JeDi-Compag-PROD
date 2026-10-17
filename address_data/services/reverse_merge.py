"""Sloučení OSM reverse geocoding s oficiální RÚIAN adresou pro výběr z mapy."""

from __future__ import annotations

import re

from catalogs.services.address import normalize_czech_address
from catalogs.services.fulfillment_address import normalize_fulfillment_address

from address_data.services.offline_persist import display_label

_BUILDING_REF = re.compile(r"^[A-Za-z]*\d+[A-Za-z0-9]*(?:/\d+[A-Za-z0-9]*)?$")


def building_ref_from_osm_tags(tags: dict | None) -> str:
    """Krátký identifikátor budovy z OSM tagů way/relation (např. M6)."""
    if not tags:
        return ""
    candidates: list[str] = []
    for key in ("name", "building:part", "ref", "short_name"):
        val = normalize_czech_address(str(tags.get(key) or ""))
        if val:
            candidates.append(val)
    for candidate in candidates:
        text = candidate.strip()
        if not text:
            continue
        if _BUILDING_REF.match(text):
            return text
        if len(text) <= 12 and re.search(r"\d", text):
            return text
    return ""


def osm_building_ref(payload: dict | None) -> str:
    """Krátký identifikátor budovy/haly z Nominatim (např. M6)."""
    if not payload:
        return ""
    address = payload.get("address") or {}
    candidates: list[str] = []
    for key in ("name", "building:part", "ref", "short_name"):
        val = normalize_czech_address(str(address.get(key) or payload.get(key) or ""))
        if val:
            candidates.append(val)
    for key in ("building", "industrial", "man_made", "amenity"):
        val = normalize_czech_address(str(address.get(key) or ""))
        if val and val.lower() not in ("yes", "industrial", "factory", "warehouse"):
            candidates.append(val)
    for candidate in candidates:
        text = candidate.strip()
        if not text:
            continue
        if _BUILDING_REF.match(text):
            return text
        if len(text) <= 12 and re.search(r"\d", text):
            return text
    return ""


def _ruian_row_from_dict(row: dict | None) -> dict | None:
    if not row:
        return None
    city = (row.get("city") or "").strip()
    street = (row.get("street") or "").strip()
    house_number = (row.get("house_number") or "").strip()
    if not city:
        return None
    if not street and city:
        street = city
    if not house_number:
        return None
    label = (row.get("label") or "").strip() or display_label(city, street, house_number)
    return {
        "city": city,
        "street": street,
        "house_number": house_number,
        "label": label,
    }


def merge_map_pin_label(
    *,
    nominatim_payload: dict | None = None,
    ruian_row: dict | None = None,
    osm_row: dict | None = None,
    building_ref: str = "",
) -> str | None:
    """
    Sestaví label pro pin na mapě: oficiální ulice + kód budovy (M6) nebo číslo popisné.
    """
    ruian = _ruian_row_from_dict(ruian_row)
    ref = (building_ref or "").strip() or osm_building_ref(nominatim_payload)

    if ruian and ref and ref != ruian["house_number"]:
        if ref.lower() in (ruian["label"] or "").lower():
            return ruian["label"]
        merged = normalize_fulfillment_address(f"{ruian['street']}, {ref}, {ruian['city']}")
        if merged:
            return merged

    if ruian:
        return ruian["label"]

    ref = (ref or "").strip()
    if osm_row:
        city = (osm_row.get("city") or "").strip()
        street = (osm_row.get("street") or "").strip()
        if not street and city:
            street = city
        if ref and street and city:
            merged = normalize_fulfillment_address(f"{street}, {ref}, {city}")
            if merged:
                return merged

    structured = _ruian_row_from_dict(osm_row)
    if structured:
        label = (osm_row or {}).get("label") or structured["label"]
        return normalize_fulfillment_address(label) or label

    return None
