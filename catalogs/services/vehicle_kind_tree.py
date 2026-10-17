"""Strom druhů vozidel — podřízenost (child_kinds) a kontrola cyklů."""

from __future__ import annotations

from collections.abc import Iterable

from catalogs.models import VehicleKindCatalog
from catalogs.services.vehicle_kind_compatibility import (
    _descendant_ids,
    clear_vehicle_kind_compatibility_cache,
)


def would_create_parent_cycle(kind_id: int, new_parent_id: int | None) -> bool:
    """True pokud by přiřazení parent_kind vytvořilo cyklus."""
    if new_parent_id is None:
        return False
    if int(kind_id) == int(new_parent_id):
        return True
    return int(new_parent_id) in _descendant_ids(int(kind_id))


def sync_child_kinds_for_parent(
    parent: VehicleKindCatalog,
    selected_children: Iterable[VehicleKindCatalog],
) -> None:
    """Nastaví parent_kind u vybraných podřízených druhů; u ostatních dětí tohoto rodiče zruší vazbu."""
    parent_id = int(parent.pk)
    selected_ids = {int(c.pk) for c in selected_children}
    current_ids = set(
        VehicleKindCatalog.objects.filter(parent_kind_id=parent_id).values_list("pk", flat=True)
    )

    for child_id in selected_ids:
        if would_create_parent_cycle(child_id, parent_id):
            raise ValueError(f"Cyklus ve stromu druhů (pk={child_id} → {parent_id}).")

    for child_id in selected_ids:
        VehicleKindCatalog.objects.filter(pk=child_id).update(parent_kind_id=parent_id)

    for child_id in current_ids - selected_ids:
        VehicleKindCatalog.objects.filter(pk=child_id, parent_kind_id=parent_id).update(
            parent_kind_id=None
        )

    clear_vehicle_kind_compatibility_cache()
