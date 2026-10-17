"""URL párovacího odkazu a generování QR (PNG data URI) — sdílené admin + číselník."""

from __future__ import annotations

import base64
import io
from typing import TYPE_CHECKING

import qrcode
from django.conf import settings
from django.urls import reverse

if TYPE_CHECKING:
    from django.http import HttpRequest
    from driver_portal.models import DriverPortalPairingToken


def relative_pairing_path(secret: str) -> str:
    return reverse("driver_portal:pair", kwargs={"secret": secret})


def absolute_pairing_url_secret(secret: str, request: HttpRequest | None = None) -> str:
    rel = relative_pairing_path(secret)
    base = (getattr(settings, "PUBLIC_BASE_URL", None) or "").strip().rstrip("/")
    if base:
        return f"{base}{rel}"
    if request is not None:
        return request.build_absolute_uri(rel)
    return rel


def absolute_pairing_url_token(obj: DriverPortalPairingToken, request: HttpRequest | None = None) -> str:
    return absolute_pairing_url_secret(obj.secret, request=request)


def pairing_url_is_relative(url: str) -> bool:
    return url.startswith("/")


def qr_png_data_uri(url: str) -> str | None:
    """Data URI obrázku QR nebo None, pokud URL není absolutní."""
    if pairing_url_is_relative(url):
        return None
    img = qrcode.make(url, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
