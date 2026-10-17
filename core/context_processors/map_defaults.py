"""Výchozí souřadnice mapy z AppSettings pro modal a skripty (globálně v šablonách)."""

from __future__ import annotations


def app_map_defaults(request):
    try:
        from core.models import AppSettings

        s = AppSettings.load()
        lat = float(s.default_map_lat)
        lng = float(s.default_map_lng)
    except Exception:
        lat, lng = 49.8175, 15.473
    return {
        "app_default_map_lat": lat,
        "app_default_map_lng": lng,
        "app_default_map_lat_js": f"{lat:.7f}",
        "app_default_map_lng_js": f"{lng:.7f}",
    }
