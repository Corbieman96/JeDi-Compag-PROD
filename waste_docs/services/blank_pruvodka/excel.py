"""Hodnoty pro Excel bianko průvodky — jen SND a datum, zbytek prázdný."""

from __future__ import annotations

from waste_docs.models import Pruvodka

from .archive import is_unused_blank_pruvodka


def is_blank_excel_minimal(ride: Pruvodka) -> bool:
    return is_unused_blank_pruvodka(ride)


def blank_excel_placeholder_values(pruvodka: Pruvodka) -> dict[str, str]:
    from waste_docs.pruvodka_services import PLACEHOLDER_MAP

    values: dict[str, str] = {token: "" for token in PLACEHOLDER_MAP}
    values["{{SND_CISLO_LISTU_}}"] = (pruvodka.snd_cislo_listu or "").strip()
    values["{{DATUM}}"] = pruvodka.drive_date.strftime("%d.%m.%Y") if pruvodka.drive_date else ""
    values["{{ADRESA_}}"] = ""
    return values
