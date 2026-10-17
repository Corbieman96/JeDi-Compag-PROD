"""Načtení ODS (VOK) a zápis pasportů kontejnerů."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction

from catalogs.models import ContainerPassport, PasportStredisko, VehicleKindCatalog
from catalogs.services.container_passport_vok_mapping import (
    parse_container_size_ft,
    parse_volume_m3,
    resolve_vok_import_to_catalog_shortcut,
    shortcut_from_sheet_name,
    vehicle_requirement_for_size_ft,
    vehicle_requirement_for_volume_m3,
)


def _strip_marks(s: str) -> str:
    n = unicodedata.normalize("NFD", (s or "").strip().lower())
    return "".join(c for c in n if unicodedata.category(c) != "Mn")


def _cell_text(cell) -> str:
    from odf import teletype

    return teletype.extractText(cell).replace("\n", " ").strip()


def _expand_row_cells(row) -> list[str]:
    from odf.table import TableCell

    vals: list[str] = []
    for cell in row.getElementsByType(TableCell):
        t = _cell_text(cell)
        # odfpy: jen normalizované jméno bez pomlček (prázdný řetězec nesmí spadnout na neplatný alias).
        rep = cell.getAttribute("numbercolumnsrepeated")
        try:
            n = max(1, int(rep)) if rep else 1
        except (TypeError, ValueError):
            n = 1
        vals.extend([t] * n)
    return vals


def read_ods_tables(path: Path) -> list[tuple[str, list[list[str]]]]:
    from odf.opendocument import load
    from odf.table import Table, TableRow

    doc = load(str(path))
    out: list[tuple[str, list[list[str]]]] = []
    for table in doc.spreadsheet.getElementsByType(Table):
        name = (table.getAttribute("name") or "").strip() or "(bez názvu)"
        rows: list[list[str]] = []
        for row in table.getElementsByType(TableRow):
            rows.append(_expand_row_cells(row))
        out.append((name, rows))
    return out


# (název pole v aplikaci, podřetězce normalizované hlavičky — stačí jedna shoda)
_HEADER_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("container_number", ("kontejner", "cislo kontejner", "cislo kont", "cislo", "container", "cont")),
    ("vok_type", ("vok", "typ vo", "typvoz", "druh voz", "druhvoz", "typ voz", "typ")),
    ("color", ("barva",)),
    ("year", ("rok", "rok vyroby", "rok výroby")),
    ("stredisko", ("stredisko", "středisko", "centrum", "zakladna", "základna")),
    ("volume_m3", ("m3", "m³", "objem", "kubik", "kubick")),
    ("size", ("velikost", "stop", " ft", "ft", "prostor")),
)


def _pick_header_row(matrix: list[list[str]], sheet_name: str) -> tuple[int, dict[str, int]] | None:
    """Vrátí index řádku hlavičky a mapu pole → index sloupce."""
    sheet_shortcut = shortcut_from_sheet_name(sheet_name)
    for ri, row in enumerate(matrix[:50]):
        if not row or not any((c or "").strip() for c in row):
            continue
        norm = [_strip_marks(c) for c in row]
        hits: dict[str, int] = {}
        for col_i, h in enumerate(norm):
            if not h:
                continue
            for field, needles in _HEADER_RULES:
                if field in hits:
                    continue
                if any(n in h for n in needles):
                    hits[field] = col_i
        has_num = "container_number" in hits
        has_typ = "vok_type" in hits
        if has_num and (has_typ or sheet_shortcut):
            return ri, hits
    return None


def _parse_year(raw: str) -> int | None:
    if not raw:
        return None
    m = re.search(r"(19|20)\d{2}", raw)
    if m:
        return int(m.group(0))
    return None


@dataclass
class VokImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    sheet_skipped: int = 0
    preview_ok: int = 0
    errors: list[str] = field(default_factory=list)


def import_container_passports_from_ods(
    path: Path,
    *,
    dry_run: bool = False,
    default_color: str = "—",
) -> VokImportResult:
    """
    Projde všechny tabulky v ODS, najde hlavičku (sloupec čísla + typ nebo jen číslo u listu pojmenovaného jako zkratka),
    vytvoří nebo aktualizuje ``ContainerPassport``.

    Druh vozidla musí odpovídat záznamům v ``VehicleKindCatalog`` (``/catalogs/vehicle-rz/kinds/``): buď přesná shoda
    zkratky s názvem listu, nebo mapování v ``VOK_SHEET_NAME_TO_KIND_SHORTCUT`` / ``settings.VOK_IMPORT_SHEET_KIND_MAP``.
    """
    result = VokImportResult()
    tables = read_ods_tables(path)
    catalog_shortcuts = frozenset(VehicleKindCatalog.objects.values_list("shortcut", flat=True))

    for sheet_name, matrix in tables:
        picked = _pick_header_row(matrix, sheet_name)
        if not picked:
            result.sheet_skipped += 1
            result.errors.append(
                f"List „{sheet_name}“: nenalezena hlavička (sloupec čísla; typ ve sloupci nebo v názvu listu)."
            )
            continue
        header_i, col_map = picked
        data_rows = matrix[header_i + 1 :]

        for r_offset, row in enumerate(data_rows):
            ri = header_i + 1 + r_offset
            try:
                def col(name: str) -> str:
                    idx = col_map.get(name)
                    if idx is None or idx >= len(row):
                        return ""
                    return (row[idx] or "").strip()

                num = col("container_number")
                if not num:
                    result.skipped += 1
                    continue

                vok_raw = col("vok_type")
                shortcut = resolve_vok_import_to_catalog_shortcut(
                    sheet_name, vok_raw, catalog_shortcuts=catalog_shortcuts
                )
                if not shortcut:
                    result.skipped += 1
                    sk = shortcut_from_sheet_name(sheet_name) or "?"
                    result.errors.append(
                        f"{sheet_name} ř. {ri + 1}: nelze namapovat na druh vozidla z číselníku "
                        f"(list „{sk}“ → doplňte zkratku v /catalogs/vehicle-rz/kinds/ nebo "
                        f"VOK_IMPORT_SHEET_KIND_MAP / VOK_SHEET_NAME_TO_KIND_SHORTCUT)."
                    )
                    continue
                vk = VehicleKindCatalog.objects.get(shortcut=shortcut)

                color = col("color") or default_color
                year = _parse_year(col("year"))

                vol_m3 = parse_volume_m3(col("volume_m3")) if col("volume_m3") else None
                size_raw = col("size")
                size_ft = parse_container_size_ft(size_raw) if size_raw else None
                if vol_m3 is not None:
                    size_ft = None
                req = vehicle_requirement_for_volume_m3(vol_m3) or vehicle_requirement_for_size_ft(size_ft)
                stredisko = None
                sc = col("stredisko")
                if sc:
                    code = sc.strip().upper()
                    if not dry_run:
                        stredisko, _ = PasportStredisko.objects.get_or_create(
                            code=code,
                            defaults={"name": "", "sort_order": 0, "is_active": True},
                        )
                    else:
                        stredisko = None

                if dry_run:
                    result.preview_ok += 1
                    continue

                with transaction.atomic():
                    obj, created = ContainerPassport.objects.update_or_create(
                        container_number=num,
                        defaults={
                            "vehicle_kind": vk,
                            "stredisko": stredisko,
                            "color": color,
                            "year_manufactured": year,
                            "volume_m3": vol_m3,
                            "container_size_ft": size_ft,
                            "vehicle_requirement_note": req,
                        },
                    )
                if created:
                    result.created += 1
                else:
                    result.updated += 1
            except Exception as exc:  # noqa: BLE001 — souhrn chyb importu
                result.skipped += 1
                result.errors.append(f"{sheet_name} ř. {ri + 1}: {exc}")

    return result
