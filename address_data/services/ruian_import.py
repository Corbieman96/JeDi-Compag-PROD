from __future__ import annotations

import json
import time
from collections.abc import Iterator
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from catalogs.services.address import normalize_czech_address

from address_data.services.ruian_geocoding import ruian_attrs_to_row

KRAJ_LAYER_URL = "https://ags.cuzk.cz/arcgis/rest/services/RUIAN/MapServer/17/query"
OKRES_LAYER_URL = "https://ags.cuzk.cz/arcgis/rest/services/RUIAN/MapServer/15/query"
PRAHA_OBVOD_LAYER_URL = "https://ags.cuzk.cz/arcgis/rest/services/RUIAN/MapServer/9/query"
ADDRESS_LAYER_URL = "https://ags.cuzk.cz/arcgis/rest/services/RUIAN/MapServer/1/query"

DEFAULT_PAGE_SIZE = 2000
PRAHA_KRAJ_KOD = 19


def _fetch_json(
    url: str,
    params: dict,
    *,
    method: str = "GET",
    timeout: int = 120,
) -> dict | None:
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
        headers={"User-Agent": "Jedis-Django/1.0 (ruian-import)"},
    )
    if method == "POST":
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    for attempt in range(1, 4):
        try:
            with urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            if attempt < 3:
                time.sleep(attempt * 1.5)
    return None


@lru_cache(maxsize=1)
def _kraj_kod_by_name() -> dict[str, int]:
    payload = _fetch_json(
        KRAJ_LAYER_URL,
        {"f": "pjson", "where": "1=1", "outFields": "kod,nazev", "returnGeometry": "false"},
        timeout=60,
    )
    out: dict[str, int] = {}
    if not payload:
        return out
    for feature in payload.get("features") or []:
        attrs = (feature or {}).get("attributes") or {}
        name = normalize_czech_address(attrs.get("nazev") or "").lower()
        kod = attrs.get("kod")
        if name and kod is not None:
            out[name] = int(kod)
    return out


def _resolve_region_kod(region_name: str) -> int | None:
    normalized = normalize_czech_address(region_name or "").lower()
    return _kraj_kod_by_name().get(normalized)


def _fetch_layer_geometries(url: str, where: str) -> list[tuple[str, dict]]:
    payload = _fetch_json(
        url,
        {
            "f": "pjson",
            "where": where,
            "outFields": "kod,nazev",
            "returnGeometry": "true",
            "outSR": "4326",
        },
        timeout=120,
    )
    if not payload:
        return []
    units: list[tuple[str, dict]] = []
    for feature in payload.get("features") or []:
        if not isinstance(feature, dict):
            continue
        attrs = feature.get("attributes") or {}
        name = normalize_czech_address(attrs.get("nazev") or "") or str(attrs.get("kod") or "")
        geometry = feature.get("geometry")
        if isinstance(geometry, dict):
            units.append((name, geometry))
    return units


def _fetch_subunit_geometries(kraj_kod: int) -> list[tuple[str, dict]]:
    if kraj_kod == PRAHA_KRAJ_KOD:
        return _fetch_layer_geometries(PRAHA_OBVOD_LAYER_URL, "1=1")
    return _fetch_layer_geometries(OKRES_LAYER_URL, f"vusc={kraj_kod}")


def _iter_addresses_in_geometry(
    geometry: dict,
    *,
    max_rows: int,
    page_size: int,
) -> Iterator[dict]:
    last_objectid = 0
    yielded = 0
    out_fields = "objectid,adresa,psc,cislodomovni,cisloorientacni,cisloorientacnipismeno,ulice"

    while yielded < max_rows:
        where = f"objectid>{last_objectid}" if last_objectid else "1=1"
        payload = _fetch_json(
            ADDRESS_LAYER_URL,
            {
                "f": "pjson",
                "where": where,
                "geometry": json.dumps(geometry),
                "geometryType": "esriGeometryPolygon",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": out_fields,
                "returnGeometry": "true",
                "outSR": "4326",
                "resultRecordCount": page_size,
                "orderByFields": "objectid",
            },
            method="POST",
            timeout=180,
        )
        if not payload:
            break
        features = payload.get("features") or []
        if not features:
            break

        page_last_objectid = last_objectid
        for feature in features:
            if not isinstance(feature, dict):
                continue
            attrs = feature.get("attributes") or {}
            objectid = attrs.get("objectid")
            if isinstance(objectid, int) and objectid > page_last_objectid:
                page_last_objectid = objectid
            geom = feature.get("geometry") or {}
            try:
                lat = float(geom["y"])
                lng = float(geom["x"])
            except (KeyError, TypeError, ValueError):
                continue
            row = ruian_attrs_to_row(attrs, lat=lat, lng=lng)
            if not row:
                continue
            yield row
            yielded += 1
            if yielded >= max_rows:
                return

        if page_last_objectid <= last_objectid:
            break
        last_objectid = page_last_objectid
        if not payload.get("exceededTransferLimit"):
            break


def iter_region_addresses(
    region_name: str,
    *,
    max_rows: int = 600_000,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Iterator[dict]:
    """Yield structured addresses for a Czech region (kraj) from RÚIAN MapServer."""
    kraj_kod = _resolve_region_kod(region_name)
    if kraj_kod is None:
        return

    subunits = _fetch_subunit_geometries(kraj_kod)
    if not subunits:
        return

    page_size = max(500, min(page_size, 2000))
    max_rows = max(1000, max_rows)
    per_unit_max = max(5000, (max_rows // len(subunits)) + 1000)
    total_yielded = 0

    for _unit_name, geometry in subunits:
        if total_yielded >= max_rows:
            break
        remaining = max_rows - total_yielded
        unit_limit = min(per_unit_max, remaining)
        for row in _iter_addresses_in_geometry(geometry, max_rows=unit_limit, page_size=page_size):
            yield row
            total_yielded += 1
            if total_yielded >= max_rows:
                return


def fetch_region_addresses(
    region_name: str,
    *,
    max_rows: int = 600_000,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> list[dict]:
    return list(iter_region_addresses(region_name, max_rows=max_rows, page_size=page_size))
