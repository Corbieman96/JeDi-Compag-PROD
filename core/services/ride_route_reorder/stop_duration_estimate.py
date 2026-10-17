"""Odhad délky zastávky (minuty na místě) pro AI prompt řazení trasy."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from catalogs.models import ActivityCatalog
from waste_docs.models import Pruvodka

from .container_labels import load_passport_map

DEFAULT_MINUTES = 20
FALLBACK_BY_NAME = (
    (("výměna", "vymena"), 35),
    (("svoz",), 20),
    (("přistaven", "pristaven"), 12),
    (("stažení", "stazeni", "stáhnout", "stahnout"), 18),
    (("odvoz",), 20),
)

_MANUAL_KEYWORDS = ("ruč", "ruc", "ruča", "ruca", "ruční", "rucni", "naklád", "naklad")
_WAIT_KEYWORDS = ("čekán", "cekan", "čekat", "cekat", "počkat", "pockat", "brán", "bran", "vrátn", "vratn")


@dataclass(frozen=True)
class StopDurationEstimate:
    minutes: int
    modifiers: tuple[str, ...] = ()


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", (value or "").strip().lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def activity_label_lower(ride: Pruvodka) -> str:
    snap = (ride.activity_snapshot or "").strip().lower()
    if snap:
        return snap
    act = getattr(ride, "activity", None)
    if act is not None:
        return (getattr(act, "name", None) or "").strip().lower()
    return ""


def is_pristaveni_style(label: str) -> bool:
    return "přistaven" in label or "pristaven" in label


def is_stazeni_style(label: str) -> bool:
    return any(t in label for t in ("stažení", "stazeni", "stáhnout", "stahnout"))


def is_vymena_style(label: str) -> bool:
    return "výměna" in label or "vymena" in label


def is_svoz_style(label: str) -> bool:
    return "svoz" in label


def _fallback_minutes_from_name(label: str) -> int:
    for patterns, minutes in FALLBACK_BY_NAME:
        if any(p in label for p in patterns):
            return minutes
    return DEFAULT_MINUTES


def load_activity_minutes_for_rides(items: list[Pruvodka]) -> dict[int, int | None]:
    """Mapa activity_id → default_service_minutes z číselníku."""
    activity_ids = {ride.activity_id for ride in items if ride.activity_id}
    if not activity_ids:
        return {}
    return {
        row["id"]: row["default_service_minutes"]
        for row in ActivityCatalog.objects.filter(pk__in=activity_ids).values(
            "id", "default_service_minutes"
        )
    }


def load_activity_minutes_by_name() -> dict[str, int]:
    """Mapa lowercase název činnosti → minuty (pro snapshot bez FK)."""
    out: dict[str, int] = {}
    for row in ActivityCatalog.objects.exclude(default_service_minutes__isnull=True).values(
        "name", "default_service_minutes"
    ):
        name = (row["name"] or "").strip().lower()
        if name and row["default_service_minutes"] is not None:
            out[name] = int(row["default_service_minutes"])
    return out


def _base_minutes(ride: Pruvodka, activity_minutes: dict[int, int | None], by_name: dict[str, int]) -> int:
    label = activity_label_lower(ride)
    if ride.activity_id and ride.activity_id in activity_minutes:
        catalog_val = activity_minutes[ride.activity_id]
        if catalog_val is not None:
            return int(catalog_val)
    act = getattr(ride, "activity", None)
    if act is not None and act.default_service_minutes is not None:
        return int(act.default_service_minutes)
    if label in by_name:
        return by_name[label]
    return _fallback_minutes_from_name(label)


def _max_container_volume(ride: Pruvodka, passport_map: dict) -> float | None:
    volumes: list[float] = []
    for num in [(ride.container_number or "").strip(), (ride.container_number_2 or "").strip()]:
        if not num:
            continue
        passport = None
        if ride.container_passport_id and (ride.container_number or "").strip() == num:
            passport = ride.container_passport
        if passport is None:
            passport = passport_map.get(num)
        if passport is not None and passport.volume_m3 is not None:
            volumes.append(float(passport.volume_m3))
    return max(volumes) if volumes else None


def _note_has_any(note_norm: str, keywords: tuple[str, ...]) -> bool:
    return any(k in note_norm for k in keywords)


def estimate_stop_duration(
    ride: Pruvodka,
    passport_map: dict,
    *,
    activity_minutes: dict[int, int | None] | None = None,
    minutes_by_name: dict[str, int] | None = None,
) -> StopDurationEstimate:
    activity_minutes = activity_minutes or {}
    minutes_by_name = minutes_by_name or {}
    label = activity_label_lower(ride)
    note_norm = _normalize_text(ride.contact_note or "")

    minutes = _base_minutes(ride, activity_minutes, minutes_by_name)
    modifiers: list[str] = []

    volume = _max_container_volume(ride, passport_map)
    if volume is not None:
        if volume >= 40:
            minutes += 10
            modifiers.append("+velký VOK")
        elif volume >= 30:
            minutes += 5
            modifiers.append("+VOK")

    has_two_containers = bool((ride.container_number or "").strip() and (ride.container_number_2 or "").strip())
    if has_two_containers and is_vymena_style(label):
        minutes += 5
        modifiers.append("+výměna 2 kont.")

    if _note_has_any(note_norm, _WAIT_KEYWORDS):
        if is_stazeni_style(label):
            minutes += 20
            modifiers.append("+čekání na místě")
        elif is_pristaveni_style(label):
            minutes += 5
            modifiers.append("+krátké čekání")

    if _note_has_any(note_norm, _MANUAL_KEYWORDS):
        if is_stazeni_style(label) or is_svoz_style(label):
            minutes += 15
            modifiers.append("+ruční nakládka")
        elif not is_pristaveni_style(label) and not is_vymena_style(label):
            minutes += 15
            modifiers.append("+ruční práce")

    minutes = max(5, minutes)
    return StopDurationEstimate(minutes=minutes, modifiers=tuple(modifiers))


def format_stop_duration_for_prompt(estimate: StopDurationEstimate) -> str:
    if estimate.modifiers:
        return f"{estimate.minutes} min ({', '.join(estimate.modifiers)})"
    return f"{estimate.minutes} min"


def _rides_by_pk(items: list[Pruvodka]) -> dict[int, Pruvodka]:
    return {ride.pk: ride for ride in items}


def _children_by_parent(items: list[Pruvodka]) -> dict[int, list[Pruvodka]]:
    by_pk = _rides_by_pk(items)
    out: dict[int, list[Pruvodka]] = {}
    for ride in items:
        parent_id = ride.follow_up_parent_id
        if parent_id and parent_id in by_pk:
            out.setdefault(parent_id, []).append(ride)
    return out


def format_follow_up_link(
    ride: Pruvodka,
    *,
    rides_by_pk: dict[int, Pruvodka],
    children_by_parent: dict[int, list[Pruvodka]],
) -> str:
    parts: list[str] = []
    parent_id = ride.follow_up_parent_id
    if parent_id and parent_id in rides_by_pk:
        parent = rides_by_pk[parent_id]
        parent_activity = (parent.activity_snapshot or "").strip() or "předchozí"
        parts.append(f"↩ navazuje na pk {parent_id} ({parent_activity})")
    children = children_by_parent.get(ride.pk) or []
    for child in children:
        child_activity = (child.activity_snapshot or "").strip() or "navazující"
        parts.append(f"→ čeká {child_activity} pk {child.pk}")
    return " | ".join(parts) if parts else "—"


def build_follow_up_pair_summary(items: list[Pruvodka]) -> list[str]:
    rides_by_pk = _rides_by_pk(items)
    pairs: list[str] = []
    for ride in items:
        parent_id = ride.follow_up_parent_id
        if not parent_id or parent_id not in rides_by_pk:
            continue
        parent = rides_by_pk[parent_id]
        parent_act = (parent.activity_snapshot or "").strip() or "?"
        child_act = (ride.activity_snapshot or "").strip() or "?"
        pairs.append(
            f"- pk {parent_id} ({parent_act}) → pk {ride.pk} ({child_act}) "
            f"u {(parent.name_snapshot or '').strip() or 'subjekt'}"
        )
    if not pairs:
        return []
    return [
        "Páry přistavení → stažení (tentýž den):",
        *pairs,
        "Mezi první a druhou návštěvou může auto obsloužit jiné zastávky (nakládka ručači probíhá mezitím).",
    ]


def prepare_follow_up_maps(items: list[Pruvodka]) -> tuple[dict[int, Pruvodka], dict[int, list[Pruvodka]]]:
    rides_by_pk = _rides_by_pk(items)
    return rides_by_pk, _children_by_parent(items)


def build_passport_map_for_rides(items: list[Pruvodka]) -> dict:
    numbers: set[str] = set()
    for ride in items:
        for num in [(ride.container_number or "").strip(), (ride.container_number_2 or "").strip()]:
            if num:
                numbers.add(num)
    return load_passport_map(numbers)
