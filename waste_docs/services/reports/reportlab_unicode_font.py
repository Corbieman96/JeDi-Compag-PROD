"""Registrace Unicode TTF pro ReportLab (čeština v PDF)."""

from __future__ import annotations

import os
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FONT_NAME = "JeDiS-Unicode"
_registered = False


def _candidate_ttf_paths() -> list[Path]:
    windir = os.environ.get("WINDIR") or r"C:\Windows"
    fonts_dir = Path(windir) / "Fonts"
    names = (
        "arial.ttf",
        "Arial.ttf",
        "calibri.ttf",
        "Calibri.ttf",
        "DejaVuSans.ttf",
        "dejavusans.ttf",
    )
    out: list[Path] = []
    for name in names:
        out.append(fonts_dir / name)
        out.append(Path(name))
    return out


def ensure_reportlab_unicode_font() -> str:
    """Vrátí jméno registrovaného Unicode fontu; při selhání Helvetica."""
    global _registered
    if _registered and _FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return _FONT_NAME
    for path in _candidate_ttf_paths():
        if not path.is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont(_FONT_NAME, str(path)))
            _registered = True
            return _FONT_NAME
        except Exception:
            continue
    return "Helvetica"
