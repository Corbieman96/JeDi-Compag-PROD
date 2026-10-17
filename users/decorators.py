"""Dekorátory pohledů podle efektivní viditelnosti menu (včetně profilu uživatele)."""

from __future__ import annotations

from django.contrib.auth.decorators import user_passes_test

from users.services.nav_visibility import (
    effective_show_address_data_nav,
    effective_show_catalogs_nav,
    effective_show_reports_nav,
    effective_show_settings_nav,
)


def catalogs_nav_required(view):
    return user_passes_test(effective_show_catalogs_nav)(view)


def settings_nav_required(view):
    return user_passes_test(effective_show_settings_nav)(view)


def address_data_nav_required(view):
    return user_passes_test(effective_show_address_data_nav)(view)


def reports_nav_required(view):
    return user_passes_test(effective_show_reports_nav)(view)
