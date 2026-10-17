"""Heuristická optimalizace pořadí zastávek v jízdě — pravidla JeDiS."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum

from catalogs.models import NameSubjectProfile
from waste_docs.models import Pruvodka

from .stop_duration_estimate import (
    activity_label_lower,
    estimate_stop_duration,
    is_pristaveni_style,
    is_stazeni_style,
    is_svoz_style,
    is_vymena_style,
)


class ActivityKind(str, Enum):
    DEPOT = "depot"
    PRISTAVIT_STAHNOUT = "pristavit_stahnout"
    PRISTAVENI = "pristaveni"
    STAZENI = "stazeni"
    VYMENA = "vymena"
    SVOZ = "svoz"
    JINA = "jina"
    OTHER = "other"


@dataclass
class RouteStop:
    ride: Pruvodka
    kind: ActivityKind
    address_key: str
    suffix_key: str
    hard_time_min: int | None = None
    soft_time_min: int | None = None
    lat: float | None = None
    lng: float | None = None
    duration_min: int = 20
    parent_pk: int | None = None
    child_pks: list[int] = field(default_factory=list)


def _normalize_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", (value or "").strip().lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _is_nic(value: str) -> bool:
    key = _normalize_key(value)
    return key in ("", "nic", "-", "—")


def is_depot_stop(ride: Pruvodka) -> bool:
    name = _normalize_key(ride.name_snapshot or "")
    if "compag" not in name or "mlada boleslav" not in name:
        return False
    return _is_nic(ride.waste_type_snapshot or "") and _is_nic(ride.suffix_snapshot or "")


def classify_activity(ride: Pruvodka) -> ActivityKind:
    if is_depot_stop(ride):
        return ActivityKind.DEPOT
    label = activity_label_lower(ride)
    label_norm = _normalize_key(label)
    if not label_norm:
        return ActivityKind.OTHER
    has_pristavit = "pristav" in label_norm
    has_stahnout = any(t in label_norm for t in ("stahn", "staz"))
    if has_pristavit and has_stahnout:
        return ActivityKind.PRISTAVIT_STAHNOUT
    if is_vymena_style(label):
        return ActivityKind.VYMENA
    if is_stazeni_style(label) or (has_stahnout and not has_pristavit):
        return ActivityKind.STAZENI
    if has_pristavit:
        return ActivityKind.PRISTAVENI
    if is_svoz_style(label):
        return ActivityKind.SVOZ
    if "jina" in label_norm:
        return ActivityKind.JINA
    return ActivityKind.OTHER


_TIME_V_RE = re.compile(
    r"\bv\s*(\d{1,2})(?:[:.](\d{2}))?\s*h\b",
    re.IGNORECASE,
)
_TIME_KOLEM_RE = re.compile(
    r"\bkolem\s*(\d{1,2})(?:[:.](\d{2}))?\s*h?\b",
    re.IGNORECASE,
)


def _parse_time_minutes(match: re.Match[str]) -> int:
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    return hour * 60 + minute


def parse_time_constraints(note: str) -> tuple[int | None, int | None]:
    text = note or ""
    hard = None
    soft = None
    m = _TIME_V_RE.search(text)
    if m:
        hard = _parse_time_minutes(m)
    m = _TIME_KOLEM_RE.search(text)
    if m:
        soft = _parse_time_minutes(m)
    return hard, soft


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_subject_coords(name_ids: set[int]) -> dict[int, tuple[float, float]]:
    if not name_ids:
        return {}
    out: dict[int, tuple[float, float]] = {}
    for profile in NameSubjectProfile.objects.filter(name_id__in=name_ids):
        lat = profile.fulfillment_latitude or profile.facility_latitude
        lng = profile.fulfillment_longitude or profile.facility_longitude
        if lat is not None and lng is not None:
            out[profile.name_id] = (float(lat), float(lng))
    return out


def build_route_stops(items: list[Pruvodka], passport_map: dict | None = None) -> list[RouteStop]:
    passport_map = passport_map or {}
    coords = load_subject_coords({r.name_id for r in items if r.name_id})
    stops: list[RouteStop] = []
    for ride in items:
        hard, soft = parse_time_constraints(ride.contact_note or "")
        lat_lng = coords.get(ride.name_id) if ride.name_id else None
        stops.append(
            RouteStop(
                ride=ride,
                kind=classify_activity(ride),
                address_key=_normalize_key(ride.address_snapshot or ""),
                suffix_key=_normalize_key(ride.suffix_snapshot or ""),
                hard_time_min=hard,
                soft_time_min=soft,
                lat=lat_lng[0] if lat_lng else None,
                lng=lat_lng[1] if lat_lng else None,
                duration_min=estimate_stop_duration(ride, passport_map).minutes,
                parent_pk=ride.follow_up_parent_id,
            )
        )
    by_pk = {s.ride.pk: s for s in stops}
    for stop in stops:
        if stop.parent_pk and stop.parent_pk in by_pk:
            by_pk[stop.parent_pk].child_pks.append(stop.ride.pk)
    return stops


def _constraints_satisfied(stop: RouteStop, ordered_pks: set[int], stops_by_pk: dict[int, RouteStop]) -> bool:
    if stop.parent_pk and stop.parent_pk not in ordered_pks:
        return False
    if stop.kind == ActivityKind.STAZENI and stop.parent_pk is None:
        for other in stops_by_pk.values():
            if other.ride.pk in ordered_pks or other.ride.pk == stop.ride.pk:
                continue
            if other.kind == ActivityKind.PRISTAVENI and other.address_key and other.address_key == stop.address_key:
                if other.ride.pk not in ordered_pks:
                    return False
    return True


def _kind_priority(kind: ActivityKind) -> int:
    return {
        ActivityKind.PRISTAVENI: 0,
        ActivityKind.PRISTAVIT_STAHNOUT: 1,
        ActivityKind.VYMENA: 2,
        ActivityKind.SVOZ: 3,
        ActivityKind.JINA: 4,
        ActivityKind.OTHER: 5,
        ActivityKind.STAZENI: 6,
        ActivityKind.DEPOT: -1,
    }.get(kind, 5)


def _score_candidate(
    stop: RouteStop,
    *,
    last: RouteStop | None,
    simulated_time_min: int,
) -> tuple:
    same_addr = 0
    same_suffix = 0
    distance = 9999.0
    if last is not None:
        if stop.address_key and stop.address_key == last.address_key:
            same_addr = 1
        if stop.suffix_key and stop.suffix_key == last.suffix_key:
            same_suffix = 1
        if (
            last.lat is not None
            and last.lng is not None
            and stop.lat is not None
            and stop.lng is not None
        ):
            distance = _haversine_km(last.lat, last.lng, stop.lat, stop.lng)

    late_penalty = 0
    if stop.hard_time_min is not None and simulated_time_min > stop.hard_time_min:
        late_penalty = simulated_time_min - stop.hard_time_min

    soft_penalty = 0
    if stop.soft_time_min is not None and simulated_time_min > stop.soft_time_min:
        soft_penalty = simulated_time_min - stop.soft_time_min

    hard_schedule = stop.hard_time_min if stop.hard_time_min is not None else 99999

    return (
        late_penalty,
        _kind_priority(stop.kind),
        hard_schedule,
        soft_penalty,
        -same_addr,
        -same_suffix,
        distance,
        stop.ride.ride_sequence,
        stop.ride.pk,
    )


def _cluster_same_address(order: list[int], stops_by_pk: dict[int, RouteStop]) -> list[int]:
    """Stejná adresa → za sebou; pořadí skupin podle prvního výskytu ve vstupu."""
    if len(order) < 2:
        return order
    by_addr: dict[str, list[int]] = {}
    for pk in order:
        addr = stops_by_pk[pk].address_key
        if addr:
            by_addr.setdefault(addr, []).append(pk)
    if not by_addr:
        return order
    result: list[int] = []
    placed: set[str] = set()
    for pk in order:
        addr = stops_by_pk[pk].address_key
        if not addr:
            result.append(pk)
        elif addr not in placed:
            result.extend(by_addr[addr])
            placed.add(addr)
    return result


def optimize_route_order(items: list[Pruvodka], *, passport_map: dict | None = None) -> list[int]:
    """
    Vrátí seznam pk průvodek v navrhovaném pořadí trasy.
    Vždy obsahuje přesně všechny pk ze vstupu, bez duplicit.
    """
    if not items:
        return []
    if len(items) == 1:
        return [items[0].pk]

    stops = build_route_stops(items, passport_map)
    stops_by_pk = {s.ride.pk: s for s in stops}
    input_pks = {s.ride.pk for s in stops}

    depots = sorted(
        [s for s in stops if s.kind == ActivityKind.DEPOT],
        key=lambda s: (s.ride.ride_sequence, s.ride.pk),
    )
    pool = {s.ride.pk for s in stops if s.kind != ActivityKind.DEPOT}
    ordered: list[int] = [s.ride.pk for s in depots]
    ordered_set = set(ordered)
    simulated_time = 8 * 60

    while pool:
        ready = [
            stops_by_pk[pk]
            for pk in pool
            if _constraints_satisfied(stops_by_pk[pk], ordered_set, stops_by_pk)
        ]
        if not ready:
            ready = [stops_by_pk[pk] for pk in pool]

        last = stops_by_pk[ordered[-1]] if ordered else None
        best = min(
            ready,
            key=lambda s: _score_candidate(s, last=last, simulated_time_min=simulated_time),
        )
        ordered.append(best.ride.pk)
        ordered_set.add(best.ride.pk)
        pool.remove(best.ride.pk)
        simulated_time += best.duration_min + 15

    ordered = _cluster_same_address(ordered, stops_by_pk)

    if set(ordered) != input_pks or len(ordered) != len(input_pks):
        raise ValueError("Optimalizace nevrátila kompletní sadu pk.")

    return ordered


def format_route_order_output(order: list[int]) -> str:
    """Výstup pouze pk, jedno na řádek — pro AI / export."""
    return "\n".join(str(pk) for pk in order)
