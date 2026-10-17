"""Normalizace textu pro case-insensitive / diakritika-nezávislé vyhledávání."""

from __future__ import annotations

import unicodedata


def normalize_search_text(value: str) -> str:
    text = (value or "").strip().lower()
    if not text:
        return ""
    decomp = unicodedata.normalize("NFKD", text)
    return "".join(
        ch for ch in decomp if not unicodedata.combining(ch) and not ch.isspace()
    )
