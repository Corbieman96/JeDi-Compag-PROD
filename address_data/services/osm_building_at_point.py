"""Budova pod pinem mapy (Overpass + point-in-polygon) → kód name/ref (např. M6)."""

from __future__ import annotations

from address_data.services.overpass_client import load_overpass_json

# Okolí pinu pro Around filtr (~35 m).
_AROUND_M = 35
# Reverse geocode: krátký timeout, jeden pokus (mapa nesmí viset).
_REVERSE_TIMEOUT_S = 8


def point_in_polygon(lat: float, lng: float, ring: list[tuple[float, float]]) -> bool:
    """Ray casting; ring = [(lat, lng), ...] (nemusí být uzavřený)."""
    if len(ring) < 3:
        return False
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-15) + xi
        ):
            inside = not inside
        j = i
    return inside


def _ref_from_tags(tags: dict) -> str:
    for key in ("name", "ref", "addr:housename"):
        val = (tags.get(key) or "").strip()
        if val:
            return val
    return ""


def _ring_from_element(el: dict) -> list[tuple[float, float]]:
    geom = el.get("geometry") or []
    ring: list[tuple[float, float]] = []
    for pt in geom:
        lat = pt.get("lat")
        lon = pt.get("lon")
        if lat is None or lon is None:
            continue
        ring.append((float(lat), float(lon)))
    return ring


def building_ref_at_point(lat: float, lng: float) -> str:
    """
    Vrátí name/ref budovy, jejíž polygon obsahuje pin.
    Při chybě Overpass nebo bez shody vrátí prázdný řetězec.
    """
    query = f"""
[out:json][timeout:{_REVERSE_TIMEOUT_S}];
(
  way(around:{_AROUND_M},{lat},{lng})["building"];
  relation(around:{_AROUND_M},{lat},{lng})["building"];
);
out geom;
"""
    data = load_overpass_json(
        query,
        timeout=_REVERSE_TIMEOUT_S,
        max_attempts=1,
    )
    if not data:
        return ""

    for el in data.get("elements") or []:
        tags = el.get("tags") or {}
        if "building" not in tags:
            continue
        ref = _ref_from_tags(tags)
        if not ref:
            continue
        ring = _ring_from_element(el)
        if ring and point_in_polygon(lat, lng, ring):
            return ref
    return ""
