"""Helpery pro ride_note v pair_hints."""

from __future__ import annotations


def pair_ride_note_hint_value(pair) -> str:
    """Text do Poznámky jízdy: ride_note, jinak yard_dispatch_note_text."""
    note = (getattr(pair, "ride_note", None) or "").strip()
    if note:
        return note[:200]
    return (getattr(pair, "yard_dispatch_note_text", None) or "").strip()[:200]


def enrich_pair_hint_with_ride_note(hint: dict, pair) -> dict:
    """Doplní do pair_hint klíče ride_note."""
    hint["ride_note"] = pair_ride_note_hint_value(pair)
    return hint
