"""Lidsky čitelný kód pozvánky (nezaměnitelné znaky)."""

from __future__ import annotations

import secrets

from django.apps import apps

_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def normalize_display_code(raw: str) -> str:
    """Sjednotí vstup pro porovnání s uloženým kódem (mezery, velikost písmen)."""
    return (raw or "").strip().upper().replace(" ", "")


def generate_unique_display_code() -> str:
    Model = apps.get_model("driver_portal", "DriverPortalPairingToken")
    for _ in range(80):
        a = "".join(secrets.choice(_ALPHABET) for _ in range(4))
        b = "".join(secrets.choice(_ALPHABET) for _ in range(4))
        code = f"{a}-{b}"
        if not Model.objects.filter(display_code=code).exists():
            return code
    raise RuntimeError("Nepodařilo se vygenerovat unikátní kód pozvánky.")
