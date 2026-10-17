"""Doplnění klonovaného listu protokolu — jen tokeny, prázdné sloty a Kde."""

from __future__ import annotations

import re
from copy import copy

TOKEN_RE = re.compile(r"\{\{[^{}]+\}\}")

PROTOCOL_LINE_BLOCK_ROWS: tuple[tuple[int, ...], ...] = (
    (4, 5, 6, 7, 8),
    (9, 10, 11, 12, 13),
    (14, 15, 16, 17, 18),
    (19, 20, 21, 22, 23),
    (24, 25, 26, 27, 28),
    (29, 30, 31, 32, 33),
    (34, 35, 36, 37, 38),
)

PROTOCOL_KDE_LABEL_COORDS = ("H5", "H10", "H15", "H20", "H25", "H30", "H35")


def _copy_cell_font_from_template(template_sheet, output_sheet, coord: str) -> None:
    tpl_cell = template_sheet[coord]
    out_cell = output_sheet[coord]
    if tpl_cell.font:
        out_cell.font = copy(tpl_cell.font)


def _token_cell_coords_in_block(template_sheet, block_rows: tuple[int, ...]) -> list[str]:
    coords: list[str] = []
    for row_num in block_rows:
        for col in range(1, 14):
            cell = template_sheet.cell(row=row_num, column=col)
            if isinstance(cell.value, str) and "{{" in cell.value and "}}" in cell.value:
                coords.append(cell.coordinate)
    return coords


def _apply_kde_suppression(sheet, lines: list[dict], template_sheet) -> None:
    for idx, coord in enumerate(PROTOCOL_KDE_LABEL_COORDS):
        if idx >= len(lines):
            break
        if lines[idx].get("suppress_kde"):
            sheet[coord].value = ""
            _copy_cell_font_from_template(template_sheet, sheet, coord)


def _clear_unused_slot_tokens(
    sheet,
    template_sheet,
    *,
    line_count: int,
) -> None:
    """Vyčistí tokenové buňky prázdných slotů 2–7 na přední straně."""
    for line_idx in range(line_count + 1, 8):
        block_rows = PROTOCOL_LINE_BLOCK_ROWS[line_idx - 1]
        for coord in _token_cell_coords_in_block(template_sheet, block_rows):
            sheet[coord].value = ""
        sheet[PROTOCOL_KDE_LABEL_COORDS[line_idx - 1]].value = ""
        first_row = block_rows[0]
        if sheet.cell(row=first_row, column=1).value not in (None, ""):
            sheet.cell(row=first_row, column=1).value = None


def fill_protocol_sheet(
    sheet,
    *,
    template_sheet,
    lines: list[dict] | None = None,
) -> None:
    """Po doplnění tokenů vyčistí prázdné sloty a skryje popisek Kde dle činnosti."""
    lines = lines or []
    _apply_kde_suppression(sheet, lines, template_sheet)
    _clear_unused_slot_tokens(sheet, template_sheet, line_count=len(lines))
