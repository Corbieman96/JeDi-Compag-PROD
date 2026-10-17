from __future__ import annotations

from catalogs.services.address import normalize_czech_address, normalize_czech_postal_code

from address_data.services.overpass_client import load_overpass_json

REGION_ALIASES = {
    "Praha": ["Hlavní město Praha", "Prague"],
    "Liberecký kraj": ["Liberecky kraj", "Liberec Region"],
    "Královéhradecký kraj": ["Kralovehradecky kraj", "Hradec Kralove Region"],
    "okres Mladá Boleslav": ["Mladá Boleslav District", "Mlada Boleslav District"],
    "okres Benešov": ["Benesov District"],
    "okres Beroun": ["Beroun District"],
    "okres Kladno": ["Kladno District"],
    "okres Kolín": ["Kolin District"],
    "okres Kutná Hora": ["Kutna Hora District"],
    "okres Mělník": ["Melnik District"],
    "okres Nymburk": ["Nymburk District"],
    "okres Praha-východ": ["Praha-vychod District", "Prague-East District"],
    "okres Praha-západ": ["Praha-zapad District", "Prague-West District"],
    "okres Příbram": ["Pribram District"],
    "okres Rakovník": ["Rakovnik District"],
}


def _format_postal_code(postcode: str) -> str:
    return normalize_czech_postal_code(postcode)


def _query_for_region(region_name: str) -> str:
    safe_name = region_name.replace('"', '\\"')
    return f"""
[out:json][timeout:240];
(
  relation["boundary"="administrative"]["name"="{safe_name}"];
  relation["boundary"="administrative"]["name:cs"="{safe_name}"];
);
map_to_area->.a;
(
  node(area.a)["addr:housenumber"]["addr:street"];
  node(area.a)["addr:housenumber"]["addr:place"];
  way(area.a)["addr:housenumber"]["addr:street"];
  way(area.a)["addr:housenumber"]["addr:place"];
  relation(area.a)["addr:housenumber"]["addr:street"];
  relation(area.a)["addr:housenumber"]["addr:place"];
);
out center;
"""


def fetch_region_addresses(region_name: str, max_rows: int = 200000) -> list[dict]:
    candidates = [region_name] + REGION_ALIASES.get(region_name, [])
    unique_candidates = list(dict.fromkeys(candidates))
    for candidate in unique_candidates:
        query = _query_for_region(candidate)
        data = load_overpass_json(query, timeout=260)
        if not data:
            continue
        out: list[dict] = []
        for el in data.get("elements", []):
            tags = el.get("tags", {}) or {}
            city = normalize_czech_address(
                tags.get("addr:city")
                or tags.get("addr:town")
                or tags.get("addr:village")
                or tags.get("addr:municipality")
                or tags.get("addr:hamlet")
                or ""
            )
            house_number = normalize_czech_address(tags.get("addr:housenumber") or "")
            street = normalize_czech_address(tags.get("addr:street") or tags.get("addr:place") or city)
            if not (street and house_number and city):
                continue
            postcode = _format_postal_code(tags.get("addr:postcode") or "")
            lat = el.get("lat")
            lng = el.get("lon")
            if lat is None or lng is None:
                center = el.get("center") or {}
                lat = center.get("lat")
                lng = center.get("lon")
            if lat is None or lng is None:
                continue
            label = normalize_czech_address(
                f"{street} {house_number}, {postcode} {city}".replace("  ", " ").strip()
            )
            out.append(
                {
                    "city": city,
                    "street": street,
                    "house_number": house_number,
                    "postal_code": postcode,
                    "label": label.strip(", "),
                    "lat": float(lat),
                    "lng": float(lng),
                }
            )
            if len(out) >= max_rows:
                break
        if out:
            return out
    return []
