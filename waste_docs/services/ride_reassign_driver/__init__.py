"""Hromadná výměna řidiče / RZ ve skupině jízd (dashboard Detail jízdy)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from waste_docs.services.ride_reassign_driver.apply import apply_ride_reassign_driver
    from waste_docs.services.ride_reassign_driver.context import build_ride_reassign_driver_context

__all__ = [
    "apply_ride_reassign_driver",
    "build_ride_reassign_driver_context",
]


def __getattr__(name: str):
    if name == "apply_ride_reassign_driver":
        from waste_docs.services.ride_reassign_driver.apply import apply_ride_reassign_driver as fn

        return fn
    if name == "build_ride_reassign_driver_context":
        from waste_docs.services.ride_reassign_driver.context import (
            build_ride_reassign_driver_context as fn,
        )

        return fn
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
