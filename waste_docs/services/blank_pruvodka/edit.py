"""Doplnění bianko průvodky → běžná jízda."""

from __future__ import annotations

from waste_docs.models import Pruvodka

from .constants import is_blank_pruvodka_activity


def maybe_clear_blank_flag(instance: Pruvodka) -> None:
    if not instance.is_blank_pruvodka:
        return
    if is_blank_pruvodka_activity(instance.activity_id):
        if instance.vehicle_rz_id or instance.driver_id:
            instance.is_blank_pruvodka = False
        return
    if instance.vehicle_rz_id or instance.driver_id:
        instance.is_blank_pruvodka = False
