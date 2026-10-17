"""Tisk PDF příloh jízdy s razítkem čísla listu a data jízdy."""

from __future__ import annotations

from .context import attachment_print_items_for_ride
from .stamp import stamp_attachment_pdf_bytes

__all__ = [
    "attachment_print_items_for_ride",
    "stamp_attachment_pdf_bytes",
]
