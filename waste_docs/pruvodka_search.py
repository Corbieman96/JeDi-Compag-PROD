"""Fulltextové vyhledávání v seznamu průvodek (GET parametr ``q``)."""

from __future__ import annotations

from django.db.models import Q

from waste_docs.services.search_normalize import normalize_search_text

MAX_SEARCH_LEN = 200

_SEARCH_BLOB_FIELDS = (
    "snd_cislo_listu",
    "name_snapshot",
    "ico_snapshot",
    "address_snapshot",
    "waste_type_snapshot",
    "waste_code_snapshot",
    "waste_category_snapshot",
    "vehicle_rz_snapshot",
    "driver_snapshot",
    "suffix_snapshot",
    "container_number",
    "container_number_2",
    "container_snapshot_2",
    "contact_phone",
    "contact_note",
    "contract_number",
    "contract_number_snapshot",
    "activity_snapshot",
    "zpo_instance_for_snd",
    "status",
    "created_by__username",
)


def _search_terms(raw: str) -> list[str]:
    text = (raw or "").strip()[:MAX_SEARCH_LEN]
    if not text:
        return []
    return [t.strip() for t in text.split() if t.strip()]


def _term_q(term: str) -> Q:
    ors = (
        Q(snd_cislo_listu__icontains=term)
        | Q(name_snapshot__icontains=term)
        | Q(ico_snapshot__icontains=term)
        | Q(address_snapshot__icontains=term)
        | Q(waste_type_snapshot__icontains=term)
        | Q(waste_code_snapshot__icontains=term)
        | Q(waste_category_snapshot__icontains=term)
        | Q(vehicle_rz_snapshot__icontains=term)
        | Q(driver_snapshot__icontains=term)
        | Q(suffix_snapshot__icontains=term)
        | Q(container_number__icontains=term)
        | Q(container_number_2__icontains=term)
        | Q(container_snapshot_2__icontains=term)
        | Q(contact_phone__icontains=term)
        | Q(contact_note__icontains=term)
        | Q(contract_number__icontains=term)
        | Q(contract_number_snapshot__icontains=term)
        | Q(activity_snapshot__icontains=term)
        | Q(zpo_instance_for_snd__icontains=term)
        | Q(status__icontains=term)
        | Q(created_by__username__icontains=term)
    )
    if term.isdigit():
        try:
            ors |= Q(pk=int(term))
        except ValueError:
            pass
    return ors


def _filter_by_icontains(qs, terms: list[str]):
    for term in terms:
        qs = qs.filter(_term_q(term))
    return qs


def _pruvodka_search_blob_from_values(row: dict) -> str:
    parts = [str(row.get("pk") or "")]
    for field in _SEARCH_BLOB_FIELDS:
        parts.append(str(row.get(field) or ""))
    return " ".join(parts)


def _filter_by_normalized(qs, terms: list[str]):
    norm_terms = [normalize_search_text(term) for term in terms]
    norm_terms = [term for term in norm_terms if term]
    if not norm_terms:
        return qs

    matching_pks: list[int] = []
    for row in qs.values("pk", *_SEARCH_BLOB_FIELDS):
        blob = normalize_search_text(_pruvodka_search_blob_from_values(row))
        if all(term in blob for term in norm_terms):
            matching_pks.append(row["pk"])
    if not matching_pks:
        return qs.none()
    return qs.filter(pk__in=matching_pks)


def filter_pruvodka_queryset_by_search(qs, raw: str):
    """
    Slova oddělená mezerou — každé musí najít shodu v některém z polí (AND mezi slovy).
    Nejdřív rychlá DB cesta (icontains); při 0 výsledcích fallback s Unicode normalizací.
    """
    terms = _search_terms(raw)
    if not terms:
        return qs

    filtered = _filter_by_icontains(qs, terms)
    if filtered.exists():
        return filtered
    return _filter_by_normalized(qs, terms)
