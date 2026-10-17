"""Definice číselníků sdílené mezi pohledy a uživatelským profilem (bez importu views)."""

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)

CATALOGS = {
    "name": ("Název F/P osoby", NameCatalog),
    "ico": ("IČO", IcoCatalog),
    "address": ("Adresa", AddressCatalog),
    "waste-type": ("Název druhu odpadu", WasteTypeCatalog),
    "waste-code": ("Katalogové číslo odpadu", WasteCodeCatalog),
    "waste-category": ("Kategorie odpadu", WasteCategoryCatalog),
    "vehicle-rz": ("RZ vozidla", VehicleRzCatalog),
    "drivers": ("Řidiči", DriverProfile),
    "suffix": ("Koncovka", SuffixCatalog),
    "activity": ("Činnost", ActivityCatalog),
}

HIDDEN_CATALOG_SLUGS = frozenset({"ico", "address", "waste-code", "waste-category"})
