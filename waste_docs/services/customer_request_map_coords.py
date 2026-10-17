"""Resolvování souřadnic pro mapu detailu zákaznického požadavku.

Pořadí zdrojů:
1. Vlastní souřadnice požadavku (fulfillment_latitude/longitude).
2. GPS subjektu (NameSubjectProfile) přiřazeného přes NameCatalog.
3. Nic (šablona pak spadne na geokód textové adresy).
"""

from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist

from customer_requests.models import CustomerRequest


def resolve_customer_request_map_coords(item: CustomerRequest):
    """Vrátí (lat, lng) nebo (None, None) podle fallback řetězce."""
    if item.fulfillment_latitude is not None and item.fulfillment_longitude is not None:
        return item.fulfillment_latitude, item.fulfillment_longitude

    try:
        profile = item.name.subject_profile
    except ObjectDoesNotExist:
        profile = None

    if profile is not None:
        lat = profile.fulfillment_latitude
        lng = profile.fulfillment_longitude
        if lat is not None and lng is not None:
            return lat, lng

    return None, None
