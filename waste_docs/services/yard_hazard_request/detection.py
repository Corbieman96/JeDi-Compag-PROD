"""Rozpoznání nebezpečného odpadu podle kategorie druhu odpadu v číselníku."""

from __future__ import annotations

from catalogs.models import NameSubjectWasteSuffixPair, WasteTypeCatalog

# Hodnoty pole WasteTypeCatalog.category (case-insensitive).
_HAZARDOUS_CATEGORY_VALUES = frozenset(
    {
        "n",
        "no",
        "nebezpečný",
        "nebezpecny",
        "nebezpečný odpad",
        "nebezpecny odpad",
    }
)


def _normalized_category(value: str | None) -> str:
    return (value or "").strip().casefold()


def is_hazardous_waste_type(waste_type: WasteTypeCatalog | None) -> bool:
    if waste_type is None:
        return False
    category = _normalized_category(waste_type.category)
    if not category:
        return False
    if category in _HAZARDOUS_CATEGORY_VALUES:
        return True
    if category.startswith("nebezpe"):
        return True
    return False


def is_hazardous_matrix_pair(pair: NameSubjectWasteSuffixPair) -> bool:
    waste_type = getattr(pair, "waste_type", None)
    if waste_type is None and pair.waste_type_id:
        waste_type = WasteTypeCatalog.objects.filter(pk=pair.waste_type_id).only("category").first()
    return is_hazardous_waste_type(waste_type)
