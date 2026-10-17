"""Příprava e-mailu se skupinovými dokumenty jízdy (.eml pro lokální poštovní klient)."""

from waste_docs.services.ride_document_email.dispatch_record import (
    cancel_group_dispatch,
    get_group_dispatch,
    group_dispatch_map_for_date,
    record_group_dispatch,
)
from waste_docs.services.ride_document_email.exclusions import is_group_emailed

__all__ = [
    "cancel_group_dispatch",
    "get_group_dispatch",
    "group_dispatch_map_for_date",
    "is_group_emailed",
    "record_group_dispatch",
]
