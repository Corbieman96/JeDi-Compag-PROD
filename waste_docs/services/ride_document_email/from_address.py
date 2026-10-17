from __future__ import annotations

from email.utils import formataddr

MISSING_SENDER_EMAIL_MSG = (
    "V přihlašovacích údajích chybí e-mail. Doplňte ho v administraci uživatelů (pole E-mail)."
)


def require_user_sender_email(user) -> str:
    email = (getattr(user, "email", None) or "").strip()
    if not email:
        raise ValueError(MISSING_SENDER_EMAIL_MSG)
    return email


def sender_display_name(user) -> str:
    full = (getattr(user, "get_full_name", lambda: "")() or "").strip()
    if full:
        return full
    username = (getattr(user, "username", None) or "").strip()
    if username:
        return username
    email = require_user_sender_email(user)
    return email.split("@", 1)[0]


def resolve_group_email_from_header(user) -> str:
    """Hlavička From ve formátu Outlooku: ``"Jméno" <email@domena>``."""
    email = require_user_sender_email(user)
    return formataddr((sender_display_name(user), email))


def sender_preview_label(user) -> str:
    """Text pro náhled odesílatele v modalu dashboardu."""
    email = (getattr(user, "email", None) or "").strip()
    if not email:
        return ""
    return resolve_group_email_from_header(user)
