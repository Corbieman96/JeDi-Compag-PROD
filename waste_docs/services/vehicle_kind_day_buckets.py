"""Sdílené buckety druhů vozidla pro denní přehledy (Řetěz / Atego / Hák)."""

from __future__ import annotations

from django.db.models import Q

from catalogs.models import VehicleKindCatalog
from catalogs.services.vehicle_kind_compatibility import compatible_kind_ids

BUCKET_ORDER = ("retez", "atego", "hak")
BUCKET_LABELS = {
    "retez": "Řetěz",
    "atego": "Atego",
    "hak": "Hák",
}


def find_anchor_kind(*, shortcuts: tuple[str, ...], name_contains: tuple[str, ...] = ()) -> VehicleKindCatalog | None:
    normalized = [s.strip().upper() for s in shortcuts if (s or "").strip()]
    if normalized:
        kind = VehicleKindCatalog.objects.filter(shortcut__in=normalized).order_by("sort_order", "pk").first()
        if kind is None:
            q = Q()
            for sc in normalized:
                q |= Q(shortcut__iexact=sc)
            kind = VehicleKindCatalog.objects.filter(q).order_by("sort_order", "pk").first()
        if kind:
            return kind
    for needle in name_contains:
        needle = (needle or "").strip()
        if not needle:
            continue
        kind = (
            VehicleKindCatalog.objects.filter(name__icontains=needle)
            .order_by("sort_order", "pk")
            .first()
        )
        if kind:
            return kind
    return None


def bucket_kind_id_sets() -> dict[str, frozenset[int]]:
    anchors = {
        "retez": find_anchor_kind(shortcuts=("R",), name_contains=("řetěz", "retez")),
        "atego": find_anchor_kind(shortcuts=("300_ATEGO", "A"), name_contains=("atego",)),
        "hak": find_anchor_kind(shortcuts=("H",), name_contains=("hák", "hak")),
    }
    return {
        key: compatible_kind_ids(anchor.pk) if anchor else frozenset()
        for key, anchor in anchors.items()
    }


def bucket_for_kind_ids(kind_ids: set[int], bucket_sets: dict[str, frozenset[int]]) -> str | None:
    for key in BUCKET_ORDER:
        if kind_ids & bucket_sets[key]:
            return key
    return None


__all__ = [
    "BUCKET_LABELS",
    "BUCKET_ORDER",
    "bucket_for_kind_ids",
    "bucket_kind_id_sets",
    "find_anchor_kind",
]
