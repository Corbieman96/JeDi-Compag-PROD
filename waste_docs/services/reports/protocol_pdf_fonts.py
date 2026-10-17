"""Normalizace fontů protokolu na Arial pro spolehlivý převod XLSX→PDF.

Šablona jizda.xlsx může mít popisky ve fontech (Play, Aptos, Aptos Black), které
nejsou na serveru nainstalované. LibreOffice je při převodu na PDF nahradí širším
fontem → popisek přeteče buňku a ořízne se. Vrácením na Arial je render deterministický.
"""

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path

FALLBACK_FONT = "Arial"
NON_PORTABLE_FONTS = frozenset({"Play", "Aptos", "Aptos Black", "Aptos Display"})

try:
    from openpyxl.styles import Font
    from openpyxl.worksheet.worksheet import Worksheet
except ImportError:
    Font = None  # type: ignore[assignment,misc]
    Worksheet = None  # type: ignore[assignment,misc]


def normalize_worksheet_fonts(ws: "Worksheet") -> int:
    """Nahradí nepřenositelné fonty za Arial; zachová bold/italic/velikost/barvu. Vrací počet změn."""
    if Font is None:
        raise RuntimeError("Knihovna openpyxl není nainstalovaná.")
    changed = 0
    for row in ws.iter_rows():
        for cell in row:
            font = cell.font
            if font is None or font.name not in NON_PORTABLE_FONTS:
                continue
            cell.font = Font(
                name=FALLBACK_FONT,
                size=font.size,
                bold=font.bold,
                italic=font.italic,
                underline=font.underline,
                strike=font.strike,
                color=font.color,
                vertAlign=font.vertAlign,
                charset=font.charset,
                family=font.family,
                scheme=None,
            )
            changed += 1
    return changed


def _replace_font_names_in_xml(xml: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        return f'{match.group(1)}val="{FALLBACK_FONT}"'

    pattern = (
        r'(<(?:\w+:)?(?:name|rFont)\s+)val="(?:'
        + "|".join(re.escape(name) for name in NON_PORTABLE_FONTS)
        + r')"'
    )
    return re.sub(pattern, _repl, xml)


def _replace_theme_typeface(xml: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        return f'{match.group(1)}typeface="{FALLBACK_FONT}"'

    pattern = (
        r'(<a:latin\s+)typeface="(?:'
        + "|".join(re.escape(name) for name in NON_PORTABLE_FONTS)
        + r')"'
    )
    return re.sub(pattern, _repl, xml)


def normalize_xlsx_fonts(xlsx_path: Path) -> int:
    """Chirurgicky přepíše nepřenositelné fonty na Arial v styles.xml a theme1.xml.

    Ostatní části archivu (logo v xl/media/, printerSettings, borders) zkopíruje beze změny.
    Vrací počet upravených částí archivu.
    """
    path = Path(xlsx_path)
    if not path.is_file():
        return 0

    with zipfile.ZipFile(path, "r") as source:
        entries = {info.filename: source.read(info.filename) for info in source.infolist()}

    changed_parts = 0
    for name in list(entries):
        lowered = name.lower()
        if lowered == "xl/styles.xml":
            text = entries[name].decode("utf-8")
            patched = _replace_font_names_in_xml(text)
            if patched != text:
                entries[name] = patched.encode("utf-8")
                changed_parts += 1
        elif lowered.startswith("xl/theme/") and lowered.endswith(".xml"):
            text = entries[name].decode("utf-8")
            patched = _replace_theme_typeface(text)
            if patched != text:
                entries[name] = patched.encode("utf-8")
                changed_parts += 1

    if not changed_parts:
        return 0

    fd, temp_name = tempfile.mkstemp(suffix=path.suffix)
    try:
        import os

        os.close(fd)
        temp_path = Path(temp_name)
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for name, data in entries.items():
                target.writestr(name, data)
        shutil.move(str(temp_path), str(path))
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise

    return changed_parts
