from __future__ import annotations

from decimal import Decimal

from django.db.models import F, Q
from django.db.models.functions import Abs

from catalogs.services.address import normalize_czech_address
from catalogs.services.geocoding import fetch_czech_addresses, reverse_geocode_czech_with_payload

from address_data.models import OfflineAddress
from address_data.services.geo_distance import REVERSE_BBOX_DELTA_DEG, REVERSE_MAX_DISTANCE_M, haversine_m
from address_data.services.offline_persist import display_label, upsert_offline_rows
from address_data.services.osm_building_at_point import building_ref_at_point
from address_data.services.reverse_merge import merge_map_pin_label
from address_data.services.ruian_geocoding import (
    ruian_find,
    ruian_geocode_single_line,
    ruian_reverse_geocode,
    ruian_suggest_addresses,
)


def _norm(value: str) -> str:
    return normalize_czech_address(value).lower()


def _offline_word_filters(words: list[str], query_norm: str) -> Q:
    if not words:
        return (
            Q(label_norm__icontains=query_norm)
            | Q(city_norm__icontains=query_norm)
            | Q(street_norm__icontains=query_norm)
            | Q(house_number__icontains=query_norm)
        )
    word_q = Q()
    for word in words:
        word_q |= (
            Q(label_norm__icontains=word)
            | Q(city_norm__icontains=word)
            | Q(street_norm__icontains=word)
            | Q(house_number__icontains=word)
        )
    return word_q


def _ruian_suggest_labels(query: str, limit: int) -> list[str]:
    remote_rows = ruian_suggest_addresses(query=query, limit=max(3, min(limit, 10)))
    if not remote_rows:
        return []
    out: list[str] = []
    for item in remote_rows:
        found = None
        magic_key = item.get("magicKey")
        if magic_key:
            found = ruian_find(magic_key)
        label = (found or {}).get("label") or item.get("label") or ""
        if found:
            upsert_offline_rows([found])
        if label and label not in out:
            out.append(label)
    return out


def suggest_addresses(query: str, limit: int = 8, preferred_city: str = "") -> list[str]:
    from django.db.models import Case, IntegerField, Value, When

    text = (query or "").strip()
    if len(text) < 2:
        return []
    query_norm = _norm(text)
    words = [word for word in query_norm.replace(",", " ").split() if len(word) >= 2]
    filters = _offline_word_filters(words, query_norm)
    qs = OfflineAddress.objects.filter(filters)
    city_hint = _norm(preferred_city) if preferred_city else ""
    street_hint = words[0] if words else query_norm
    qs = qs.annotate(
        street_priority=Case(
            When(street_norm__istartswith=street_hint, then=Value(0)),
            When(street_norm__icontains=street_hint, then=Value(1)),
            When(label_norm__istartswith=query_norm, then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    )
    if city_hint and city_hint != "cesko":
        qs = qs.annotate(
            city_priority=Case(
                When(city_norm__icontains=city_hint, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by("city_priority", "street_priority", "city", "street", "house_number")
    else:
        qs = qs.order_by("street_priority", "city", "street", "house_number")
    rows = qs[: max(1, min(limit, 20))]
    result: list[str] = []
    for row in rows:
        candidate = display_label(row.city, row.street, row.house_number)
        if candidate and candidate not in result:
            result.append(candidate)
    if result:
        return result

    ruian_labels = _ruian_suggest_labels(query=text, limit=limit)
    if ruian_labels:
        return ruian_labels[:limit]

    remote_rows = fetch_czech_addresses(query=text, limit=max(3, min(limit, 10)))
    if remote_rows:
        upsert_offline_rows(remote_rows)
        out: list[str] = []
        for row in remote_rows:
            candidate = display_label(row.get("city", ""), row.get("street", ""), row.get("house_number", ""))
            if candidate and candidate not in out:
                out.append(candidate)
        return out
    return []


def geocode_address(query: str) -> dict | None:
    text = (query or "").strip()
    if len(text) < 2:
        return None
    query_norm = _norm(text)
    hit = OfflineAddress.objects.filter(
        Q(label_norm__icontains=query_norm)
        | Q(city_norm__icontains=query_norm)
        | Q(street_norm__icontains=query_norm)
        | Q(house_number__icontains=query_norm)
    ).order_by("city", "street", "house_number").first()
    if hit:
        return {
            "lat": float(hit.lat),
            "lng": float(hit.lng),
            "label": display_label(hit.city, hit.street, hit.house_number),
        }

    ruian_hit = ruian_geocode_single_line(text)
    if ruian_hit:
        upsert_offline_rows([ruian_hit])
        return {
            "lat": float(ruian_hit["lat"]),
            "lng": float(ruian_hit["lng"]),
            "label": ruian_hit["label"],
        }

    remote_rows = fetch_czech_addresses(query=text, limit=1)
    if remote_rows:
        upsert_offline_rows(remote_rows)
        first = remote_rows[0]
        return {
            "lat": float(first["lat"]),
            "lng": float(first["lng"]),
            "label": display_label(first.get("city", ""), first.get("street", ""), first.get("house_number", "")),
        }
    return None


def _offline_candidates_near(lat: float, lng: float):
    delta = REVERSE_BBOX_DELTA_DEG
    return OfflineAddress.objects.filter(
        lat__gte=Decimal(str(lat - delta)),
        lat__lte=Decimal(str(lat + delta)),
        lng__gte=Decimal(str(lng - delta)),
        lng__lte=Decimal(str(lng + delta)),
    )


def _reverse_geocode_offline(lat: float, lng: float) -> dict | None:
    best_hit = None
    best_dist = float("inf")
    for hit in _offline_candidates_near(lat, lng).iterator():
        dist = haversine_m(lat, lng, float(hit.lat), float(hit.lng))
        if dist < best_dist:
            best_dist = dist
            best_hit = hit
    if not best_hit or best_dist > REVERSE_MAX_DISTANCE_M:
        return None
    return {
        "lat": lat,
        "lng": lng,
        "label": display_label(best_hit.city, best_hit.street, best_hit.house_number),
    }


def reverse_geocode(lat: float, lng: float) -> dict | None:
    ruian_hit = ruian_reverse_geocode(lat=lat, lng=lng)
    if ruian_hit:
        upsert_offline_rows([ruian_hit])

    osm_row, nominatim_payload = reverse_geocode_czech_with_payload(lat=lat, lng=lng)
    if osm_row:
        city = (osm_row.get("city") or "").strip()
        street = (osm_row.get("street") or "").strip()
        house_number = (osm_row.get("house_number") or "").strip()
        if not street and city:
            street = city
        if city and house_number:
            osm_row = {**osm_row, "street": street, "label": display_label(city, street, house_number)}

    building_ref = building_ref_at_point(lat=lat, lng=lng)
    label = merge_map_pin_label(
        nominatim_payload=nominatim_payload,
        ruian_row=ruian_hit,
        osm_row=osm_row,
        building_ref=building_ref,
    )
    if label:
        rows_to_store = []
        if ruian_hit:
            rows_to_store.append(ruian_hit)
        if osm_row and osm_row.get("city") and (osm_row.get("house_number") or label):
            rows_to_store.append({**osm_row, "lat": lat, "lng": lng, "label": label})
        if rows_to_store:
            upsert_offline_rows(rows_to_store)
        return {"lat": lat, "lng": lng, "label": label}

    offline_hit = _reverse_geocode_offline(lat=lat, lng=lng)
    if offline_hit:
        return offline_hit

    return None


def city_from_coords(lat: float, lng: float) -> str:
    lat_d = Decimal(str(lat))
    lng_d = Decimal(str(lng))
    hit = (
        OfflineAddress.objects.annotate(
            distance=Abs(F("lat") - lat_d) + Abs(F("lng") - lng_d)
        )
        .order_by("distance", "city", "street")
        .first()
    )
    if not hit:
        return "Česko"
    return (hit.city or "Česko").strip() or "Česko"
