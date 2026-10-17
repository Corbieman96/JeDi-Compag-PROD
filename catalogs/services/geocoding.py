import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from catalogs.services.address import normalize_czech_address, normalize_czech_postal_code


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def _format_postal_code(postcode: str) -> str:
    return normalize_czech_postal_code(postcode)


def _build_czech_label(street: str, house_number: str, city: str, postal_code: str) -> str:
    left = " ".join(part for part in [street, house_number] if part).strip()
    right = " ".join(part for part in [postal_code, city] if part).strip()
    if left and right:
        return normalize_czech_address(f"{left}, {right}")
    return normalize_czech_address(left or right)


def _to_human_cz(item: dict) -> str:
    address = item.get("address", {}) or {}
    road = normalize_czech_address(address.get("road") or "")
    house_number = normalize_czech_address(address.get("house_number") or "")
    postcode = _format_postal_code(address.get("postcode") or "")
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("hamlet")
    )
    city = normalize_czech_address(city or "")

    label = _build_czech_label(road, house_number, city, postcode)
    if label:
        return label

    display_name = item.get("display_name", "")
    first_chunk = display_name.split(",")[0] if display_name else ""
    return normalize_czech_address(first_chunk)


def _street_from_address(address: dict) -> str:
    road = normalize_czech_address(address.get("road") or "")
    if road:
        return road
    for key in ("building", "amenity", "office", "public_building", "place", "name"):
        val = normalize_czech_address(address.get(key) or "")
        if val:
            return val
    return ""


def _components_cz(item: dict) -> dict:
    address = item.get("address", {}) or {}
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("hamlet")
        or ""
    )
    street = _street_from_address(address)
    house_number = address.get("house_number") or ""
    postcode = _format_postal_code(address.get("postcode") or "")
    return {
        "city": normalize_czech_address(city),
        "street": normalize_czech_address(street),
        "house_number": normalize_czech_address(house_number),
        "postal_code": normalize_czech_postal_code(postcode),
    }


def fetch_czech_addresses(query: str, limit: int = 20) -> list[dict]:
    """Return structured Czech addresses from OpenStreetMap Nominatim."""
    params = urlencode(
        {
            "q": query,
            "countrycodes": "cz",
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": max(1, min(limit, 5000)),
        }
    )
    request = Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": "Jedis-Django/1.0 (offline-address-import)"},
    )
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return []
    out: list[dict] = []
    for item in payload:
        label = _to_human_cz(item)
        if not label:
            continue
        try:
            lat = float(item["lat"])
            lng = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        row = _components_cz(item)
        row.update({"label": label, "lat": lat, "lng": lng})
        out.append(row)
    return out


def suggest_czech_addresses(query: str, limit: int = 5) -> list[str]:
    """Suggest addresses in Czechia from OpenStreetMap Nominatim."""
    params = urlencode(
        {
            "q": query,
            "countrycodes": "cz",
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": max(1, min(limit, 10)),
        }
    )
    request = Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": "Jedis-Django/1.0"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return []
    results: list[str] = []
    for item in payload:
        candidate = _to_human_cz(item)
        if candidate and candidate not in results:
            results.append(candidate)
    return results


def geocode_czech_address(query: str) -> dict | None:
    params = urlencode(
        {
            "q": query,
            "countrycodes": "cz",
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": 1,
        }
    )
    request = Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": "Jedis-Django/1.0"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    if not payload:
        return None
    first = payload[0]
    try:
        return {
            "lat": float(first["lat"]),
            "lng": float(first["lon"]),
            "label": _to_human_cz(first),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _fetch_reverse_nominatim_payload(lat: float, lng: float) -> dict | None:
    params = urlencode(
        {
            "lat": lat,
            "lon": lng,
            "format": "jsonv2",
            "addressdetails": 1,
            "zoom": 18,
        }
    )
    request = Request(
        f"https://nominatim.openstreetmap.org/reverse?{params}",
        headers={"User-Agent": "Jedis-Django/1.0"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("error"):
        return None
    return payload


def reverse_geocode_czech_with_payload(lat: float, lng: float) -> tuple[dict | None, dict | None]:
    """Vrátí (strukturovaný řádek, surový Nominatim payload)."""
    payload = _fetch_reverse_nominatim_payload(lat, lng)
    if not payload:
        return None, None
    row = _components_cz(payload)
    row["lat"] = lat
    row["lng"] = lng
    row["label"] = _to_human_cz(payload)
    return row, payload


def reverse_geocode_czech_row(lat: float, lng: float) -> dict | None:
    """Structured Czech address row from OSM reverse geocode (pin coordinates preserved)."""
    payload = _fetch_reverse_nominatim_payload(lat, lng)
    if not payload:
        return None
    row = _components_cz(payload)
    row["lat"] = lat
    row["lng"] = lng
    return row


def reverse_geocode_czech(lat: float, lng: float) -> dict | None:
    payload = _fetch_reverse_nominatim_payload(lat, lng)
    if not payload:
        return None
    return {
        "lat": float(payload.get("lat", lat)),
        "lng": float(payload.get("lon", lng)),
        "label": _to_human_cz(payload),
    }
