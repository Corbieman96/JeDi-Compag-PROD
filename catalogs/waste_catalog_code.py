"""Zobrazení katalogového kódu odpadu (ČR): NN NN NN nebo NN NN NN NN, volitelně *."""

from __future__ import annotations

import re


def normalize_waste_catalog_code(raw: str | None) -> str:
    """
    Vrátí jen číselný kód s mezerami po dvojicích a volitelnou hvězdičkou na konci.
    Nepatřící text (např. za „ - „) se zahodí. Nepodaří-li se rozpoznat 6 nebo 8 číslic, vrátí "".
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if " - " in s:
        s = s.split(" - ", 1)[0].strip()
    t = s.replace(" ", "")
    has_star = t.endswith("*")
    if has_star:
        t = t[:-1]
    digits = re.sub(r"\D", "", t)
    if len(digits) >= 8:
        seq = digits[:8]
        groups = [seq[i : i + 2] for i in range(0, 8, 2)]
    elif len(digits) >= 6:
        seq = digits[:6]
        groups = [seq[i : i + 2] for i in range(0, 6, 2)]
    else:
        return ""
    body = " ".join(groups)
    return f"{body}*" if has_star else body
