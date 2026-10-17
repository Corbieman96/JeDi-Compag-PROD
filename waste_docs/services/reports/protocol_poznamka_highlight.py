"""Zvýraznění vyplněných buněk POZNAMKA_* v protokolu jizda.xlsx před tiskem/PDF."""

from __future__ import annotations

from copy import copy

from waste_docs.services.reports.protocol_sheet_bounds import iter_protocol_cells

POZNAMKA_FILL_RGB = "FF9999"
POZNAMKA_TEXT_RGB = "000000"
POZNAMKA_TOKEN_MARKER = "{{POZNAMKA_"


def poznamka_coords_from_template(template_sheet) -> tuple[str, ...]:
    """Souřadnice buněk s placeholderem {{POZNAMKA_N}} ve šabloně."""
    coords: list[str] = []
    for cell in iter_protocol_cells(template_sheet):
        value = cell.value
        if isinstance(value, str) and POZNAMKA_TOKEN_MARKER in value:
            coords.append(cell.coordinate)
    return tuple(coords)


def _cell_fill_rgb(cell) -> str:
    fill = getattr(cell, "fill", None)
    if fill is None or getattr(fill, "fill_type", None) != "solid":
        return ""
    fg = getattr(fill, "fgColor", None)
    if fg is None:
        return ""
    rgb = getattr(fg, "rgb", None)
    if not rgb:
        return ""
    text = str(rgb).upper()
    if len(text) == 8:
        return text[2:] if text.startswith("00") else text[-6:]
    return text


def _black_font_from_existing(existing) -> object:
    from openpyxl.styles import Font

    if existing is None:
        return Font(name="Arial", color=POZNAMKA_TEXT_RGB)
    return Font(
        name=existing.name or "Arial",
        size=existing.size,
        bold=existing.bold,
        italic=existing.italic,
        underline=existing.underline,
        strike=existing.strike,
        color=POZNAMKA_TEXT_RGB,
        vertAlign=existing.vertAlign,
        charset=existing.charset,
        family=existing.family,
        scheme=existing.scheme,
    )


def apply_poznamka_highlight(sheet, *, template_sheet) -> int:
    """
    Buňky POZNAMKA s neprázdným textem: pozadí #FF9999, text černý.
    Prázdné buňky beze změny. Vrací počet zvýrazněných buněk.
    """
    highlighted = 0
    for coord in poznamka_coords_from_template(template_sheet):
        cell = sheet[coord]
        if not str(cell.value or "").strip():
            continue
        from openpyxl.styles import PatternFill

        cell.fill = PatternFill(fill_type="solid", fgColor=POZNAMKA_FILL_RGB)
        cell.font = _black_font_from_existing(copy(cell.font) if cell.font else None)
        highlighted += 1
    return highlighted
