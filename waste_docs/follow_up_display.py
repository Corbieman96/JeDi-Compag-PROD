"""Zobrazení sloupce návaznost (symboly u vazby na rodiče / na navazující jízdy)."""

from __future__ import annotations

_DEFAULT_PARENT = "\u2191"  # ↑
_DEFAULT_CHILD = "\u2193"  # ↓
_EXCHANGE_FALLBACK_PARENT = "\u21c4"  # ⇄
_EXCHANGE_FALLBACK_CHILD = "\u2195"  # ↕
_STAZENI_FALLBACK_PARENT = "\u21a9"  # ↩ návrat / dovnitř (ne „ven“)


def activity_label_lower(pruvodka) -> str:
    snap = (getattr(pruvodka, "activity_snapshot", None) or "").strip().lower()
    if snap:
        return snap
    act = getattr(pruvodka, "activity", None)
    if act is not None:
        return (getattr(act, "name", None) or "").strip().lower()
    return ""


def is_exchange_style_follow_up(pruvodka) -> bool:
    """Zpětná kompatibilita, pokud v číselníku není vyplněný vlastní symbol."""
    label = activity_label_lower(pruvodka)
    return "výměna" in label or "vymena" in label


def is_stazeni_style_follow_up(pruvodka) -> bool:
    """Stažení / odvoz kontejneru zpět — výchozí symbol „návrat“ (dovnitř), ne obecná šipka nahoru."""
    label = activity_label_lower(pruvodka)
    return any(t in label for t in ("stažení", "stazeni", "stáhnout", "stahnout"))


def _stripped_catalog_symbol(raw: str | None, max_len: int = 8) -> str:
    s = (raw or "").strip()
    return s[:max_len] if s else ""


def _activity(pruvodka):
    return getattr(pruvodka, "activity", None)


def follow_up_parent_symbol_is_custom(pruvodka) -> bool:
    act = _activity(pruvodka)
    if act is None:
        return False
    return bool(_stripped_catalog_symbol(getattr(act, "follow_up_symbol_parent", None)))


def follow_up_child_symbol_is_custom(pruvodka) -> bool:
    act = _activity(pruvodka)
    if act is None:
        return False
    return bool(_stripped_catalog_symbol(getattr(act, "follow_up_symbol_child", None)))


def follow_up_parent_link_symbol(pruvodka) -> str:
    """Symbol před odkazem na rodiče: číselník → výměna → stažení → výchozí nahoru."""
    if not getattr(pruvodka, "follow_up_parent_id", None):
        return ""
    act = _activity(pruvodka)
    if act is not None:
        custom = _stripped_catalog_symbol(getattr(act, "follow_up_symbol_parent", None))
        if custom:
            return custom
    if is_exchange_style_follow_up(pruvodka):
        return _EXCHANGE_FALLBACK_PARENT
    if is_stazeni_style_follow_up(pruvodka):
        return _STAZENI_FALLBACK_PARENT
    return _DEFAULT_PARENT


def follow_up_child_link_symbol(pruvodka) -> str:
    """Symbol před odkazy na navazující průvodky (řádek rodiče)."""
    act = _activity(pruvodka)
    if act is not None:
        custom = _stripped_catalog_symbol(getattr(act, "follow_up_symbol_child", None))
        if custom:
            return custom
    if is_exchange_style_follow_up(pruvodka):
        return _EXCHANGE_FALLBACK_CHILD
    return _DEFAULT_CHILD
