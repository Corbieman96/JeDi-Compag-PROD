"""Parsování pole kontejnerů v matici hlášení — jedna položka = jeden požadavek."""

from __future__ import annotations


def non_empty_container_entries(raw: str) -> list[str]:
    """
    Každá položka = jeden SvozTask.

    Řádky v textovém poli; na jednom řádku lze více čísel oddělených čárkou nebo středníkem.
    """
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    entries: list[str] = []
    for ln in text.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        for part in ln.replace(";", ",").split(","):
            part = part.strip()
            if part:
                entries.append(part)
    return entries


__all__ = ["non_empty_container_entries"]
