"""Přístup k TXT výcucu — jen Admin / superuser."""

from __future__ import annotations

from users.constants import ROLE_ADMIN
from users.services.roles import get_user_role_label


def user_can_period_txt_digest(user) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return get_user_role_label(user) == ROLE_ADMIN
