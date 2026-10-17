"""Kontrola druhu vozidla u navazující jízdy (stejný, silnější, nebo jeden z kombinace 1. části)."""

from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist

from catalogs.models.vehicle_rz import VehicleRzCatalog, VehicleRzProfile
from catalogs.services.vehicle_kind_compatibility import (
    follow_up_allowed_kind_ids,
    profile_vehicle_kind_ids,
)


def vehicle_kind_ids_for_rz(vehicle_rz: VehicleRzCatalog | None) -> set[int]:
    if not vehicle_rz:
        return set()
    try:
        profile = vehicle_rz.profile
    except ObjectDoesNotExist:
        profile = VehicleRzProfile.objects.filter(rz=vehicle_rz).prefetch_related("vehicle_kinds").first()
    return profile_vehicle_kind_ids(profile)


def allowed_follow_kind_ids_for_parent_rz(vehicle_rz: VehicleRzCatalog | None) -> set[int]:
    """Množina druhů vozidel přípustných na RZ navazující jízdy."""
    kind_ids = vehicle_kind_ids_for_rz(vehicle_rz)
    if not kind_ids:
        return set()
    out: set[int] = set()
    for kind_id in kind_ids:
        out |= set(follow_up_allowed_kind_ids(kind_id))
    return out


def rz_vehicle_kinds_compatible_for_follow_up(
    parent_vehicle_rz: VehicleRzCatalog | None,
    follow_vehicle_rz: VehicleRzCatalog | None,
) -> bool:
    """True, pokud navazující RZ má aspoň jeden druh slučitelný s některým druhem 1. části.

    U kombinace (H+A+O) stačí Atego (A). Slabší vozidlo mimo kombinaci (jen H po 3H) neprojde.
    """
    if not parent_vehicle_rz or not follow_vehicle_rz:
        return True
    follow_kinds = vehicle_kind_ids_for_rz(follow_vehicle_rz)
    if not follow_kinds:
        return True
    allowed = allowed_follow_kind_ids_for_parent_rz(parent_vehicle_rz)
    if not allowed:
        return True
    return bool(follow_kinds & allowed)


def _kind_labels(kind_ids: set[int]) -> str:
    if not kind_ids:
        return "—"
    from catalogs.models import VehicleKindCatalog

    labels = []
    for row in VehicleKindCatalog.objects.filter(pk__in=kind_ids).order_by("sort_order", "name", "pk"):
        labels.append(row.display_label() if hasattr(row, "display_label") else str(row))
    return ", ".join(labels) if labels else "—"


def follow_up_vehicle_kind_error(
    *,
    parent_vehicle_rz: VehicleRzCatalog | None,
    follow_vehicle_rz: VehicleRzCatalog | None,
) -> str | None:
    """Vrátí chybovou hlášku, pokud navazující RZ nemá slučitelný druh vozidla s 1. částí."""
    if not parent_vehicle_rz or not follow_vehicle_rz:
        return None
    if rz_vehicle_kinds_compatible_for_follow_up(parent_vehicle_rz, follow_vehicle_rz):
        return None
    parent_kinds = vehicle_kind_ids_for_rz(parent_vehicle_rz)
    follow_kinds = vehicle_kind_ids_for_rz(follow_vehicle_rz)
    parent_rz = (getattr(parent_vehicle_rz, "value", None) or "").strip() or "—"
    follow_rz = (getattr(follow_vehicle_rz, "value", None) or "").strip() or "—"
    return (
        f"Navazující jízda musí jet vozidlem stejného nebo silnějšího druhu jako 1. část "
        f"({parent_rz}: {_kind_labels(parent_kinds)}). "
        f"Zvolené RZ {follow_rz} má druh {_kind_labels(follow_kinds)} — nelze navázat."
    )
