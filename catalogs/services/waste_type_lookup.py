"""Dohledání WasteTypeCatalog z textu comboboxu (kód, label, fuzzy shoda)."""

from __future__ import annotations

import re
import unicodedata

from catalogs.models import WasteTypeCatalog
from catalogs.services.waste_type_labels import waste_type_combo_metadata
from catalogs.waste_catalog_code import normalize_waste_catalog_code

_DASH_RE = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\-]+")


def normalize_waste_combo_text(raw: str) -> str:
    """Sjednotí mezery a pomlčky pro porovnání labelů."""
    text = unicodedata.normalize("NFKC", (raw or "").strip())
    if not text:
        return ""
    text = _DASH_RE.sub(" — ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*—\s*", " — ", text)
    return text.strip()


def normalize_waste_searchable(raw: str) -> str:
    """Stejná idea jako JS normalizeWasteQuery — bez mezer, lowercase."""
    text = normalize_waste_combo_text(raw).lower()
    return re.sub(r"[^0-9a-záčďéěíňóôřšťúůýž*+]", "", text.replace(" ", ""))


def _metadata_entries(allowed_ids: set[int] | None = None) -> list[tuple[int, dict]]:
    meta = waste_type_combo_metadata()
    out: list[tuple[int, dict]] = []
    for pk_str, row in meta.items():
        pk = int(pk_str)
        if allowed_ids is not None and pk not in allowed_ids:
            continue
        out.append((pk, row))
    return out


def resolve_waste_type_from_combo_text(
    text: str,
    *,
    allowed_ids: set[int] | None = None,
) -> WasteTypeCatalog | None:
    """Vrátí odpad podle textu z comboboxu nebo None."""
    raw = (text or "").strip()
    if not raw:
        return None

    entries = _metadata_entries(allowed_ids)
    if not entries:
        entries = _metadata_entries(None)

    normalized = normalize_waste_combo_text(raw)

    # 1) Přesná shoda labelu
    label_to_pk = {row["label"]: pk for pk, row in entries}
    if normalized in label_to_pk:
        return WasteTypeCatalog.objects.filter(pk=label_to_pk[normalized]).first()

    # 2) Shoda po sjednocení pomlček u všech labelů
    norm_label_map: dict[str, int] = {}
    for pk, row in entries:
        norm_label_map[normalize_waste_combo_text(row["label"])] = pk
    if normalized in norm_label_map:
        return WasteTypeCatalog.objects.filter(pk=norm_label_map[normalized]).first()

    # 3) Podle normalizovaného kódu
    code_norm = normalize_waste_catalog_code(raw)
    if code_norm:
        code_matches = [pk for pk, row in entries if row.get("code") == code_norm]
        if len(code_matches) == 1:
            return WasteTypeCatalog.objects.filter(pk=code_matches[0]).first()

    # 4) Searchable text — jednoznačná shoda
    nq = normalize_waste_searchable(raw)
    if nq:
        searchable_hits: list[int] = []
        for pk, row in entries:
            searchable = normalize_waste_searchable(f"{row.get('code', '')} {row.get('label', '')}")
            if nq in searchable or searchable in nq:
                searchable_hits.append(pk)
        if len(searchable_hits) == 1:
            return WasteTypeCatalog.objects.filter(pk=searchable_hits[0]).first()

    # 5) Prefix labelu (uživatel dopíše mezeru / kurzor)
    prefix_hits = [
        pk for pk, row in entries
        if normalize_waste_combo_text(row["label"]).startswith(normalized)
    ]
    if len(prefix_hits) == 1:
        return WasteTypeCatalog.objects.filter(pk=prefix_hits[0]).first()

    return None
