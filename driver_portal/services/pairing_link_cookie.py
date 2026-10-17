"""Podepsané cookie pro opakované přihlášení přes stejný odkaz z QR po úspěšném párování."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import HttpRequest, HttpResponse

from driver_portal.models import DriverPortalPairingToken
from users.constants import ROLE_RIDIC
from users.services.access_profile import get_access_profile
from users.services.roles import get_user_role_label

User = get_user_model()

COOKIE_NAME = "dp_plink"
MAX_AGE_SECONDS = 60 * 60 * 24 * 180  # 180 dní
SIGN_SALT = "driver_portal.pairing_link_v1"
COOKIE_PATH = "/driver-portal/"


def set_pairing_link_cookie(
    response: HttpResponse,
    request: HttpRequest,
    user,
    token: DriverPortalPairingToken,
) -> None:
    """Nastaví cookie jen když je účet aktivně spárovaný s řidičem z pozvánky."""
    if token.status != DriverPortalPairingToken.Status.ACTIVE:
        return
    if get_user_role_label(user) != ROLE_RIDIC:
        return
    prof = get_access_profile(user)
    if prof.driver_profile_id != token.driver_id:
        return

    signer = TimestampSigner(salt=SIGN_SALT)
    value = signer.sign(f"{user.pk}:{token.pk}")
    secure = getattr(settings, "SESSION_COOKIE_SECURE", False) or request.is_secure()
    response.set_cookie(
        COOKIE_NAME,
        value,
        max_age=MAX_AGE_SECONDS,
        path=COOKIE_PATH,
        httponly=True,
        samesite="Lax",
        secure=secure,
    )


def try_user_from_pairing_link_cookie(
    request: HttpRequest,
    token: DriverPortalPairingToken,
):
    """Vrátí uživatele jen při platném cookie pro tuto pozvánku a stále platném spárování."""
    if token.status != DriverPortalPairingToken.Status.ACTIVE:
        return None

    raw = request.COOKIES.get(COOKIE_NAME)
    if not raw:
        return None

    signer = TimestampSigner(salt=SIGN_SALT)
    try:
        payload = signer.unsign(raw, max_age=MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None

    parts = payload.split(":", 1)
    if len(parts) != 2:
        return None
    try:
        user_id = int(parts[0])
        token_pk = int(parts[1])
    except ValueError:
        return None

    if token_pk != token.pk:
        return None

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return None

    if not user.is_active or get_user_role_label(user) != ROLE_RIDIC:
        return None

    prof = get_access_profile(user)
    if prof.driver_profile_id != token.driver_id:
        return None

    return user


def clear_pairing_link_cookie(response: HttpResponse, request: HttpRequest) -> None:
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH)
