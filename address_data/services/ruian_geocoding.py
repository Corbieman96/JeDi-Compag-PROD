from __future__ import annotations

import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from catalogs.services.address import normalize_czech_address, normalize_czech_postal_code
from catalogs.services.fulfillment_address import normalize_fulfillment_address

from address_data.services.geo_distance import REVERSE_MAX_DISTANCE_M, haversine_m
from address_data.services.query_variants import build_query_variants

GEOCODE_SOE_URL = "https://ags.cuzk.cz/arcgis/rest/services/RUIAN/MapServer/exts/GeocodeSOE"
ADDRESS_LAYER_URL = "https://ags.cuzk.cz/arcgis/rest/services/RUIAN/MapServer/1/query"

RUIAN_ADDR_PATTERN = re.compile(
    r"^(?P<left>.+?),\s*(?:(?P<mcast>[^,\d][^,]*),\s*)?(?P<psc>\d{5})\s+(?P<city>.+)$"
)
_HOUSE_NUMBER = r"[A-Za-z]*\d+[A-Za-z0-9]*(?:/\d+[A-Za-z0-9]*)?"
_LEFT_NUMBER_PATTERN = re.compile(rf"(?P<number>{_HOUSE_NUMBER})\s*$")


def _fetch_json(url: str, params: dict | None = None, *, method: str = "GET", timeout: int = 12) -> dict | list | None:
    params = params or {}
    if method == "GET":
        request_url = f"{url}?{urlencode(params)}" if params else url
        data = None
    else:
        request_url = url
        data = urlencode(params).encode()
    req = Request(
        request_url,
        data=data,
        method=method,
        headers={"User-Agent": "Jedis-Django/1.0 (ruian-geocoding)"},
    )
    if method == "POST":
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    payload = None
    for attempt in range(1, 4):
        try:
            with urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            break
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            if attempt < 3:
                time.sleep(attempt * 1.2)
    return payload if isinstance(payload, (dict, list)) else None


def _format_house_number(attrs: dict) -> str:
    dom = attrs.get("cislodomovni")
    if dom is None:
        return ""
    ori = attrs.get("cisloorientacni")
    pismeno = (attrs.get("cisloorientacnipismeno") or "").strip()
    if ori:
        return f"{dom}/{ori}{pismeno}"
    return f"{dom}{pismeno}"


def _normalize_ruian_postal_code(value) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return f"{value:05d}"
    text = str(value).strip()
    if text.isdigit() and len(text) <= 5:
        return f"{int(text):05d}"
    return normalize_czech_postal_code(text)


def _street_from_left(left: str, house_number: str, city: str) -> str:
    left = normalize_czech_address(left)
    left = re.sub(r"^č\.?\s*p\.?\s*", "", left, flags=re.I)
    left = re.sub(r"^č\.?\s*ev\.?\s*", "", left, flags=re.I).strip()
    if house_number and left.endswith(house_number):
        left = left[: -len(house_number)].strip()
    left = left.strip(" ,")
    return left or city


def ruian_text_to_strict_label(text: str) -> str:
    """Convert RÚIAN label e.g. 'Rostkov 1, 29413 Chocnějovice' to app strict format."""
    row = ruian_text_to_row(text)
    return row.get("label", "") if row else normalize_fulfillment_address(text)


def ruian_text_to_row(text: str, lat: float | None = None, lng: float | None = None) -> dict | None:
    adresa = normalize_czech_address(text or "")
    match = RUIAN_ADDR_PATTERN.match(adresa)
    if not match:
        return None
    city = normalize_czech_address(match.group("city"))
    postal_code = _normalize_ruian_postal_code(match.group("psc"))
    left = match.group("left").strip()
    number_match = _LEFT_NUMBER_PATTERN.search(left)
    if not number_match:
        return None
    house_number = normalize_czech_address(number_match.group("number"))
    street = normalize_czech_address(_street_from_left(left, house_number, city))
    if not city or not house_number:
        return None
    if not street:
        street = city
    label = normalize_fulfillment_address(f"{street}, {house_number}, {city}")
    row = {
        "city": city,
        "street": street,
        "house_number": house_number,
        "postal_code": postal_code,
        "label": label,
    }
    if lat is not None and lng is not None:
        row["lat"] = lat
        row["lng"] = lng
    return row


def ruian_attrs_to_row(attrs: dict, lat: float, lng: float) -> dict | None:
    adresa = normalize_czech_address(attrs.get("adresa") or "")
    match = RUIAN_ADDR_PATTERN.match(adresa)
    if not match:
        return None
    city = normalize_czech_address(match.group("city"))
    psc_raw = attrs.get("psc") if attrs.get("psc") is not None else match.group("psc")
    postal_code = _normalize_ruian_postal_code(psc_raw)
    house_number = normalize_czech_address(_format_house_number(attrs))
    if not city or not house_number:
        return None
    street = normalize_czech_address(_street_from_left(match.group("left"), house_number, city))
    if not street:
        street = city
    label = normalize_fulfillment_address(f"{street}, {house_number}, {city}")
    return {
        "city": city,
        "street": street,
        "house_number": house_number,
        "postal_code": postal_code,
        "label": label,
        "lat": lat,
        "lng": lng,
    }


def ruian_suggest(text: str) -> list[dict]:
    payload = _fetch_json(f"{GEOCODE_SOE_URL}/suggest", {"text": text, "f": "json"})
    if not isinstance(payload, dict):
        return []
    suggestions = payload.get("suggestions") or []
    return [item for item in suggestions if isinstance(item, dict)]


def ruian_find(magic_key: str) -> dict | None:
    payload = _fetch_json(
        f"{GEOCODE_SOE_URL}/findAddressCandidates",
        {"magicKey": magic_key, "outSR": 4326, "f": "json"},
    )
    if not isinstance(payload, dict):
        return None
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        attrs = candidate.get("attributes") or {}
        if (attrs.get("Type") or "").strip() not in ("", "AdresniMisto"):
            continue
        location = candidate.get("location") or {}
        try:
            lng = float(location["x"])
            lat = float(location["y"])
        except (KeyError, TypeError, ValueError):
            continue
        address_text = normalize_czech_address(candidate.get("address") or attrs.get("Match_addr") or "")
        row = ruian_text_to_row(address_text, lat=lat, lng=lng)
        if row:
            return row
    return None


def ruian_suggest_addresses(query: str, limit: int = 8) -> list[dict]:
    results: list[dict] = []
    seen_keys: set[str] = set()
    for variant in build_query_variants(query):
        for item in ruian_suggest(variant):
            if (item.get("type") or "") != "AdresniMisto":
                continue
            key = str(item.get("magicKey") or item.get("text") or "")
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            text = normalize_czech_address(item.get("text") or "")
            label = ruian_text_to_strict_label(text)
            if not label:
                continue
            results.append({"text": text, "label": label, "magicKey": key})
            if len(results) >= limit:
                return results
    return results


def ruian_geocode_single_line(query: str) -> dict | None:
    for item in ruian_suggest_addresses(query, limit=6):
        found = ruian_find(item["magicKey"])
        if found:
            return found
    return None


def ruian_reverse_geocode(lat: float, lng: float) -> dict | None:
    payload = _fetch_json(
        ADDRESS_LAYER_URL,
        {
            "f": "pjson",
            "geometry": f"{lng},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "distance": 20,
            "units": "esriSRUnit_Meter",
            "outFields": "adresa,psc,cislodomovni,cisloorientacni,cisloorientacnipismeno,ulice",
            "returnGeometry": "true",
            "outSR": "4326",
        },
        timeout=15,
    )
    if not isinstance(payload, dict):
        return None
    features = payload.get("features") or []
    best: dict | None = None
    best_dist = float("inf")
    for feature in features:
        if not isinstance(feature, dict):
            continue
        attrs = feature.get("attributes") or {}
        geometry = feature.get("geometry") or {}
        try:
            feat_lat = float(geometry["y"])
            feat_lng = float(geometry["x"])
        except (KeyError, TypeError, ValueError):
            continue
        dist = haversine_m(lat, lng, feat_lat, feat_lng)
        if dist >= best_dist:
            continue
        row = ruian_attrs_to_row(attrs, lat=feat_lat, lng=feat_lng)
        if row:
            best = row
            best_dist = dist
    if best is None or best_dist > REVERSE_MAX_DISTANCE_M:
        return None
    return best
