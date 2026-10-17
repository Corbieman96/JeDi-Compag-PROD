"""Vytváření a změna stavu pozvánek s kontrolou vazby na řidiče."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone

from driver_portal.models import DriverPortalPairingToken


def create_token_for_driver(*, driver_id: int, note: str = "") -> DriverPortalPairingToken:
    return DriverPortalPairingToken.objects.create(
        driver_id=driver_id,
        note=(note or "").strip()[:200],
    )


def set_token_status_for_driver(*, token_id: int, driver_id: int, status: str) -> DriverPortalPairingToken:
    token = get_object_or_404(DriverPortalPairingToken, pk=token_id, driver_id=driver_id)
    allowed = {c.value for c in DriverPortalPairingToken.Status}
    if status not in allowed:
        raise ValueError("Neplatný stav pozvánky.")
    token.status = status
    if status == DriverPortalPairingToken.Status.ACTIVE:
        token.revoked_at = None
    else:
        token.revoked_at = timezone.now()
    token.save(update_fields=["status", "revoked_at"])
    return token
