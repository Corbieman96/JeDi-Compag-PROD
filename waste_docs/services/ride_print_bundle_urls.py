"""URL helper pro stránku tisku jízdní skupiny (datum + RZ + řidič)."""

from __future__ import annotations

from django.urls import reverse


def ride_print_bundle_url(
    *,
    selected_date,
    vehicle_rz_id: int,
    filter_pks: list[int] | None = None,
    driver_id: int | None = None,
) -> str:
    params = f"date={selected_date.isoformat()}&vehicle_rz_id={vehicle_rz_id}"
    if driver_id is not None:
        params += f"&driver_id={int(driver_id or 0)}"
    if filter_pks:
        params += f"&pks={','.join(str(p) for p in filter_pks)}"
    return f"{reverse('waste_docs:ride_print_bundle')}?{params}"
