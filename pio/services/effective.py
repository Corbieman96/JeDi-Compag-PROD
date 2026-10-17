"""Veřejné API pro zobrazení aktuálního PIO u páru subjekt–odpad–koncovka."""

from __future__ import annotations

from catalogs.models import NameSubjectWasteSuffixPair


def effective_pio_file(pair: NameSubjectWasteSuffixPair | None):
    """
    Aktivní soubor PIO pro tisk u jízdy — pouze pole ``pio_document`` na páru.

    Historické revize v archivu se pro tisk nepoužívají (zůstávají k nahlédnutí).
    """
    if not pair:
        return None
    if pair.pio_document and getattr(pair.pio_document, "name", None):
        return pair.pio_document
    return None
