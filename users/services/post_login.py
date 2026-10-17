"""Výchozí cíl po přihlášení podle role a viditelnosti menu."""

from __future__ import annotations

from urllib.parse import urlparse

from django.contrib.auth.models import AbstractBaseUser
from django.urls import reverse

from users.constants import ROLE_RIDIC, ROLE_ZADAVATEL
from users.services.access_profile import get_access_profile
from users.services.nav_visibility import (
    effective_show_catalogs_nav,
    effective_show_customer_requests_nav,
    effective_show_dashboard_nav,
    effective_show_pruvodky_nav,
)
from users.services.roles import get_user_role_label
from users.services.sberny_dvur import can_create_svoz_request
from users.services.waste_doc_permissions import can_access_waste_docs_list


def default_post_login_url(user: AbstractBaseUser) -> str:
    role = get_user_role_label(user)
    if role == ROLE_RIDIC:
        prof = get_access_profile(user)
        if prof.driver_profile_id:
            return reverse("driver_portal:day_list")
    if can_create_svoz_request(user):
        return reverse("waste_docs:yard_hub")
    if role == ROLE_ZADAVATEL:
        if effective_show_customer_requests_nav(user):
            return reverse("waste_docs:customer_request_list")
        if effective_show_pruvodky_nav(user):
            return reverse("waste_docs:list")
        if effective_show_dashboard_nav(user):
            return reverse("core:dashboard")
        if effective_show_catalogs_nav(user):
            return reverse("catalogs:index")
        return reverse("core:help")
    if effective_show_dashboard_nav(user):
        return reverse("core:dashboard")
    if effective_show_pruvodky_nav(user):
        return reverse("waste_docs:list")
    if effective_show_customer_requests_nav(user):
        return reverse("waste_docs:customer_request_list")
    if effective_show_catalogs_nav(user):
        return reverse("catalogs:index")
    return reverse("core:help")


def _path(url: str) -> str:
    return urlparse(url).path.rstrip("/") or "/"


def is_allowed_post_login_url(user: AbstractBaseUser, url: str) -> bool:
    """Ověří, zda je bezpečné poslat uživatele na `next` po přihlášení."""
    if not url:
        return False
    path = _path(url)
    if path == "/":
        return effective_show_dashboard_nav(user)
    if path.startswith("/waste-docs"):
        if path in ("/waste-docs", "/waste-docs/list/jizdy.xlsx"):
            return can_access_waste_docs_list(user)
        if path.startswith("/waste-docs/customer") or "/pozadav" in path:
            return effective_show_customer_requests_nav(user)
        if path.startswith("/waste-docs/svoz") or path.startswith("/waste-docs/sberny-dvur") or path.endswith("/yard"):
            return can_create_svoz_request(user)
        if path.startswith("/waste-docs/") and path[len("/waste-docs/") :].split("/")[0].isdigit():
            return can_access_waste_docs_list(user)
        return can_access_waste_docs_list(user)
    if path.startswith("/catalogs"):
        return effective_show_catalogs_nav(user)
    if path.startswith("/settings"):
        from users.services.nav_visibility import effective_show_settings_nav

        return effective_show_settings_nav(user)
    if path.startswith("/reports"):
        from users.services.nav_visibility import effective_show_reports_nav

        return effective_show_reports_nav(user)
    if path.startswith("/address-data"):
        from users.services.nav_visibility import effective_show_address_data_nav

        return effective_show_address_data_nav(user)
    if path in ("/help", reverse("core:help").rstrip("/")):
        return True
    if path.startswith("/driver-portal"):
        return get_user_role_label(user) == ROLE_RIDIC
    return True


def resolve_post_login_url(user: AbstractBaseUser, candidate: str | None) -> str:
    if candidate and is_allowed_post_login_url(user, candidate):
        return candidate
    return default_post_login_url(user)
