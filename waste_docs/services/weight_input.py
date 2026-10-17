"""Parsování a formátování hmotnosti (tuny) — použití primárně u nova-jizda ze sběrného dvora."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def parse_weight_t(raw: str) -> Decimal | None:
    """Přijme např. 10,36 nebo 10.36 (tuny); jinak None."""
    text = (raw or "").strip().replace("\u00a0", " ").replace(" ", "")
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value


def format_weight_snapshot(value: Decimal) -> str:
    """Český zápis pro Excel snapshot — bez zbytečných nul."""
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def weight_must_be_positive_error(value: Decimal | None) -> str | None:
    if value is None:
        return "Zadejte hmotnost v tunách (např. 10,36)."
    if value <= 0:
        return "Hmotnost musí být větší než 0."
    return None
