"""Kontext řádku matice F/P u navazující jízdy — dědění z 1. části."""

from __future__ import annotations

from waste_docs.models import Pruvodka
from waste_docs.services.follow_up_vehicle_kind import rz_vehicle_kinds_compatible_for_follow_up


def preferred_pair_id_for_follow_up(parent: Pruvodka | None) -> int | None:
    if not parent or not parent.source_waste_suffix_pair_id:
        return None
    return int(parent.source_waste_suffix_pair_id)


def follow_up_inherits_parent_pair(
    parent: Pruvodka | None,
    follow_vehicle_rz,
    *,
    manual_rz: bool,
) -> bool:
    """True, pokud 2. část pokračuje stejnou/slučitelnou soupravou jako 1. část
    a má použít řádek matice z rodiče (bez ruční změny RZ).
    """
    if not parent or manual_rz or not follow_vehicle_rz:
        return False
    if not rz_vehicle_kinds_compatible_for_follow_up(parent.vehicle_rz, follow_vehicle_rz):
        return False
    if parent.source_waste_suffix_pair_id:
        return True
    return bool(parent.vehicle_rz_id and follow_vehicle_rz.pk == parent.vehicle_rz_id)
