"""Štítky a metadata druhů odpadu pro comboboxy (kód + text)."""

from catalogs.models import WasteTypeCatalog
from catalogs.waste_catalog_code import normalize_waste_catalog_code


def waste_type_combo_metadata():
    """Slovník ``str(pk) -> {code, category, label}`` pro JSON v šabloně."""
    out = {}
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
        out[str(item.pk)] = {
            "code": code_disp,
            "category": item.category or "",
            "label": label,
        }
    return out
