"""Jednotné zobrazení druhu vozidla v UI a hláškách."""

from __future__ import annotations

from catalogs.models import VehicleKindCatalog


def format_vehicle_kind_label(kind: VehicleKindCatalog | None) -> str:
    if kind is None:
        return "—"
    return kind.display_label()


def vehicle_kind_label(obj: VehicleKindCatalog) -> str:
    return obj.display_label()


def bind_vehicle_kind_select_labels(form, *field_names: str) -> None:
    """Nastaví v ChoiceField/M2M popisky „Název (zkratka)“."""
    for name in field_names:
        field = form.fields.get(name)
        if field is not None and hasattr(field, "label_from_instance"):
            field.label_from_instance = vehicle_kind_label
