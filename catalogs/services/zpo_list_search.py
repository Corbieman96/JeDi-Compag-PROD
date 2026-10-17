"""Vyhledávání v knihovně ZPO — popisek i kód odpadu (190904 i 19 09 04)."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from catalogs.models import ZpoDocument
from catalogs.waste_catalog_code import normalize_waste_catalog_code


def zpo_search_terms(q: str) -> list[str]:
    """Varianty dotazu: původní text, normalizovaný kód s mezerami i bez mezer."""
    raw = (q or "").strip()
    if not raw:
        return []

    terms: list[str] = [raw]
    normalized = normalize_waste_catalog_code(raw)
    if normalized:
        terms.append(normalized)
        compact = normalized.replace(" ", "").replace("*", "")
        if compact:
            terms.append(compact)
    else:
        digits_only = "".join(ch for ch in raw if ch.isdigit())
        if len(digits_only) >= 6:
            spaced = normalize_waste_catalog_code(digits_only)
            if spaced:
                terms.append(spaced)
            terms.append(digits_only)

    seen: set[str] = set()
    out: list[str] = []
    for term in terms:
        key = term.casefold()
        if term and key not in seen:
            seen.add(key)
            out.append(term)
    return out


def filter_zpo_documents_for_query(qs: QuerySet[ZpoDocument], q: str) -> QuerySet[ZpoDocument]:
    terms = zpo_search_terms(q)
    if not terms:
        return qs
    cond = Q()
    for term in terms:
        cond |= Q(label__icontains=term)
        cond |= Q(waste_type__code__icontains=term)
        cond |= Q(waste_type__value__icontains=term)
        cond |= Q(suffix__value__icontains=term)
    return qs.filter(cond).distinct()
