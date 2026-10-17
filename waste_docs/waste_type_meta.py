"""Mapa druhů odpadu pro našeptávač ve formuláři nové průvodky."""

from __future__ import annotations

from catalogs.models import WasteTypeCatalog
from catalogs.waste_catalog_code import normalize_waste_catalog_code


def waste_type_meta_for_pruvodka_form() -> dict[str, dict]:
    """pk (str) → { code, category, label }."""
    waste_type_meta: dict[str, dict] = {}
    for item in WasteTypeCatalog.objects.order_by("code", "value"):
        code_disp = normalize_waste_catalog_code(item.code) or ""
        val = (item.value or "").strip()
        if code_disp and val:
            label = f"{code_disp} — {val}"
        elif code_disp:
            label = code_disp
        elif val:
            label = val
        else:
            label = f"Druh odpadu #{item.pk}"
        waste_type_meta[str(item.pk)] = {
            "code": code_disp,
            "category": item.category or "",
            "label": label,
        }
    return waste_type_meta
