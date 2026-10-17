"""
Řádky zobrazené na /catalogs/ — jednotný seznam pro šablony i uživatelský profil.
"""

from __future__ import annotations

from typing import Any

from catalogs.catalog_definitions import CATALOGS, HIDDEN_CATALOG_SLUGS


SLUG_OFFLINE_ADDRESSES = "offline_addresses"
SLUG_RIDE_TEMPLATES = "ride_templates"
SLUG_CUSTOMER_REQUEST_TEMPLATES = "customer_request_templates"
SLUG_CONTAINER_PASSPORT = "container_passport"
SLUG_PASPORT_STREDISKO = "pasport_stredisko"
SLUG_ZPO_LIBRARY = "zpo_library"

_SPECIAL_LABELS = {
    SLUG_OFFLINE_ADDRESSES: "Adresní číselník (offline DB)",
    SLUG_RIDE_TEMPLATES: "Šablony jízd",
    SLUG_CUSTOMER_REQUEST_TEMPLATES: "Šablony požadavků",
    SLUG_CONTAINER_PASSPORT: "Pasport kontejnerů",
    SLUG_PASPORT_STREDISKO: "Střediska pasportů",
    SLUG_ZPO_LIBRARY: "Knihovna ZPO",
}

# (nadpis skupiny pro tabulku, pořadí slugů řádků)
CATALOG_INDEX_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Subjekty a lokality", ("name", "suffix")),
    ("Adresní data", (SLUG_OFFLINE_ADDRESSES,)),
    ("Odpady", ("waste-type",)),
    ("Doprava", ("vehicle-rz", "drivers")),
    ("Činnost a šablony", ("activity", SLUG_RIDE_TEMPLATES, SLUG_CUSTOMER_REQUEST_TEMPLATES)),
    ("Dokumentace", (SLUG_CONTAINER_PASSPORT, SLUG_PASPORT_STREDISKO, SLUG_ZPO_LIBRARY)),
)


def catalog_row_label(slug: str) -> str:
    """Text sloupce „Číselník“ pro daný slug (katalogové nebo virtuální)."""
    if slug in CATALOGS:
        return str(CATALOGS[slug][0])
    try:
        return _SPECIAL_LABELS[slug]
    except KeyError as exc:
        raise KeyError(f"Neznámý slug řádku přehledu číselníků: {slug}") from exc


def iter_index_slugs_ordered() -> tuple[str, ...]:
    """Všechny slugy řádků v pořadí zobrazení (včetně virtuálních)."""
    return tuple(slug for _, slugs in CATALOG_INDEX_SECTIONS for slug in slugs)


def catalog_index_rows():
    """(slug, název pro UI) v pořadí přehledu — pro profil / catnav_*."""
    ordered = list(iter_index_slugs_ordered())
    seen = set(ordered)
    for slug in ordered:
        yield slug, catalog_row_label(slug)
    for slug in CATALOGS:
        if slug not in HIDDEN_CATALOG_SLUGS and slug not in seen:
            yield slug, catalog_row_label(slug)


def visible_catalog_index_sections(user: Any):
    """Sekce a řádky viditelné pro uživatele (pro /catalogs/ tabulku)."""
    from users.services.catalog_row_visibility import (
        effective_show_catalog_index_row,
        effective_show_offline_addresses_catalog_row,
    )

    def _slug_visible(slug: str) -> bool:
        if slug == SLUG_PASPORT_STREDISKO and not getattr(user, "is_superuser", False):
            return False
        if slug in CATALOGS:
            return slug not in HIDDEN_CATALOG_SLUGS and effective_show_catalog_index_row(user, slug)
        if slug == SLUG_OFFLINE_ADDRESSES:
            return effective_show_offline_addresses_catalog_row(user)
        return effective_show_catalog_index_row(user, slug)

    out = []
    for title, slugs in CATALOG_INDEX_SECTIONS:
        rows = []
        for slug in slugs:
            if not _slug_visible(slug):
                continue
            rows.append({"slug": slug, "label": catalog_row_label(slug)})
        if rows:
            out.append({"title": title, "rows": rows})
    catalog_slugs_in_layout = frozenset(
        slug for _, slugs in CATALOG_INDEX_SECTIONS for slug in slugs if slug in CATALOGS
    )
    extra = []
    for slug in CATALOGS:
        if slug in HIDDEN_CATALOG_SLUGS or slug in catalog_slugs_in_layout:
            continue
        if not effective_show_catalog_index_row(user, slug):
            continue
        extra.append({"slug": slug, "label": catalog_row_label(slug)})
    if extra:
        out.append({"title": None, "rows": extra})
    return out
