"""Geodetické vzdálenosti pro reverse geocoding (metry)."""

from __future__ import annotations

import math

# Maximální vzdálenost pinu od adresního bodu, aby se adresa použila.
REVERSE_MAX_DISTANCE_M = 25.0

# Přibližný rozsah bbox filtru (~35 m u středních šířek).
REVERSE_BBOX_DELTA_DEG = 0.00035


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Vzdálenost dvou bodů na Zemi v metrech."""
    r = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
