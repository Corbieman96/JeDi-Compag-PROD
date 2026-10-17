"""Kontext pro stránku tisku (ride_print_bundle / dashboard-bulk)."""

from __future__ import annotations

from django.urls import reverse


def build_bulk_print_config(
    *,
    selected_date_iso: str,
    vehicle_rz_id: int = 0,
    driver_id: int | str | None = None,
    filter_pks: list[int] | None = None,
) -> dict:
    driver_out = "" if driver_id is None else str(driver_id)
    pks = filter_pks or []
    return {
        "merge_url": reverse("waste_docs:bulk_merged_print_pdf"),
        "date": selected_date_iso,
        "vehicle_rz_id": int(vehicle_rz_id or 0),
        "driver_id": driver_out,
        "filter_pks": ",".join(str(p) for p in pks),
    }
