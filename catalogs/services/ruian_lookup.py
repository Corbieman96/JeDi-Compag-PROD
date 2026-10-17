from __future__ import annotations

import json
import re
import time
from html import unescape
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from catalogs.services.address import normalize_czech_address

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
OBCE_DATA_URL = "https://data.cesko.digital/obce/1/obce.json"
RUIAN_ORP_LAYER_URL = "https://ags.cuzk.cz/arcgis/rest/services/RUIAN/MapServer/14/query"
CISORP_URL = "https://apl.czso.cz/iSMS/cisdet.jsp"


def _fetch_json(url: str, params: dict, timeout: int = 12) -> dict | list | None:
    params = urlencode(params)
    request_url = f"{url}?{params}" if params else url
    req = Request(
        request_url,
        headers={"User-Agent": "Jedis-Django/1.0 (nominatim-ruian-lookup)"},
    )
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


def _fetch_text(url: str, params: dict, timeout: int = 12) -> str:
    request_url = f"{url}?{urlencode(params)}" if params else url
    req = Request(
        request_url,
        headers={"User-Agent": "Jedis-Django/1.0 (nominatim-ruian-lookup)"},
    )
    body = ""
    for attempt in range(1, 4):
        try:
            with urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
            break
        except (HTTPError, URLError, TimeoutError):
            if attempt < 3:
                time.sleep(attempt * 1.2)
    return body


def _extract_orp(address: dict) -> str:
    # Nominatim usually returns county as "SO ORP <name>".
    county = normalize_czech_address(address.get("county") or "")
    if county.lower().startswith("so orp "):
        return county[7:].strip()
    municipality = normalize_czech_address(address.get("municipality") or "")
    if municipality.lower().startswith("so orp "):
        return municipality[7:].strip()
    return county or municipality


def _extract_municipality(address: dict) -> str:
    for key in ("city", "town", "village", "municipality", "hamlet"):
        value = normalize_czech_address(address.get(key) or "")
        if value:
            if value.lower().startswith("so poú "):
                continue
            return value
    return ""


@lru_cache(maxsize=1)
def _municipality_code_map() -> dict[str, str]:
    payload = _fetch_json(OBCE_DATA_URL, params={}, timeout=20)
    if not isinstance(payload, dict):
        return {}
    municipalities = payload.get("municipalities") or []
    out: dict[str, str] = {}
    for item in municipalities:
        if not isinstance(item, dict):
            continue
        code = str((item.get("adresaUradu") or {}).get("obecKod") or "").strip()
        if not code:
            continue
        for key in (
            item.get("hezkyNazev"),
            item.get("nazev"),
        ):
            normalized = normalize_czech_address(key or "").lower()
            if normalized:
                out[normalized] = code
    return out


@lru_cache(maxsize=1)
def _orp_code_map() -> dict[str, str]:
    payload = _fetch_json(
        RUIAN_ORP_LAYER_URL,
        {
            "f": "pjson",
            "where": "1=1",
            "outFields": "kod,nazev",
            "returnGeometry": "false",
        },
        timeout=20,
    )
    if not isinstance(payload, dict):
        return {}
    features = payload.get("features") or []
    out: dict[str, str] = {}
    for item in features:
        attrs = (item or {}).get("attributes") or {}
        code = str(attrs.get("kod") or "").strip()
        name = normalize_czech_address(attrs.get("nazev") or "").lower()
        if code and name:
            out[name] = code
    return out


def _orp_by_point(lat: float, lng: float) -> tuple[str, str]:
    payload = _fetch_json(
        RUIAN_ORP_LAYER_URL,
        {
            "f": "pjson",
            "geometry": f"{lng},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "kod,nazev",
            "returnGeometry": "false",
        },
        timeout=12,
    )
    if not isinstance(payload, dict):
        return ("", "")
    features = payload.get("features") or []
    if not features:
        return ("", "")
    attrs = (features[0] or {}).get("attributes") or {}
    return (str(attrs.get("kod") or "").strip(), normalize_czech_address(attrs.get("nazev") or ""))


@lru_cache(maxsize=512)
def _cisorp_code_by_name(orp_name: str) -> str:
    normalized_name = normalize_czech_address(orp_name or "").strip().lower()
    if not normalized_name:
        return ""
    html = _fetch_text(
        CISORP_URL,
        {
            "kodcis": "65",
            "fnazev": orp_name,
            "razeni": "na",
            "delka_strany": "200",
        },
        timeout=16,
    )
    if not html:
        return ""
    row_pattern = re.compile(
        r'<td class="nowrap">\s*(\d+)\s*</td>\s*<td>\s*<a [^>]*>\s*([^<]+?)\s*</a>',
        flags=re.IGNORECASE,
    )
    best_partial = ""
    for code, raw_name in row_pattern.findall(html):
        candidate = normalize_czech_address(unescape(raw_name) or "").strip().lower()
        if not candidate:
            continue
        if candidate == normalized_name:
            return code
        if normalized_name in candidate or candidate in normalized_name:
            if not best_partial:
                best_partial = code
    return best_partial


def resolve_orp_and_iczuj(query: str = "", lat: float | None = None, lng: float | None = None) -> dict[str, str]:
    """Resolve ORP and IČZÚJ from address context."""
    out = {"orp": "", "iczuj": ""}
    address: dict = {}
    if lat is not None and lng is not None:
        payload = _fetch_json(
            NOMINATIM_REVERSE_URL,
            {
                "lat": lat,
                "lon": lng,
                "format": "jsonv2",
                "addressdetails": 1,
            },
            timeout=12,
        )
        if isinstance(payload, dict):
            address = payload.get("address") or {}
    if not address and query:
        payload = _fetch_json(
            NOMINATIM_SEARCH_URL,
            {
                "q": query,
                "countrycodes": "cz",
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": 1,
            },
            timeout=12,
        )
        if isinstance(payload, list) and payload:
            first = payload[0] or {}
            address = first.get("address") or {}
            if lat is None or lng is None:
                try:
                    lat = float(str(first.get("lat") or "").replace(",", "."))
                    lng = float(str(first.get("lon") or "").replace(",", "."))
                except (TypeError, ValueError):
                    lat = lat if lat is not None else None
                    lng = lng if lng is not None else None

    municipality_name = _extract_municipality(address)
    orp_name = _extract_orp(address)
    if orp_name:
        # Preferred output format in app: CISORP code (e.g. 2115), not RUIAN ORP code.
        out["orp"] = _cisorp_code_by_name(orp_name)
        if not out["orp"]:
            # Legacy fallback when CISORP page lookup fails.
            out["orp"] = _orp_code_map().get(orp_name.lower(), "")
    # Fallback: Nominatim often returns only district; resolve ORP by point.
    if not out["orp"] and lat is not None and lng is not None:
        ruian_orp_code, ruian_orp_name = _orp_by_point(lat=lat, lng=lng)
        out["orp"] = _cisorp_code_by_name(ruian_orp_name) if ruian_orp_name else ""
        if not out["orp"]:
            out["orp"] = ruian_orp_code
    if municipality_name:
        out["iczuj"] = _municipality_code_map().get(municipality_name.lower(), "")
    return out
