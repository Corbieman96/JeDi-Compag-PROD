"""Snapshot subjektu F/P pro formulář zákaznického požadavku (filtr odpadů, pair hints)."""

from __future__ import annotations

from catalogs.services.name_subject_pruvodka_snapshot import (
    profile_queryset_for_pruvodka_snapshot,
    subject_snapshot_for_pruvodka,
)


def subject_snapshot_for_customer_request_form(*, name_id: int | None) -> dict | None:
    if not name_id:
        return None
    profile = profile_queryset_for_pruvodka_snapshot().filter(name_id=name_id).first()
    if not profile:
        return None
    return subject_snapshot_for_pruvodka(profile)
