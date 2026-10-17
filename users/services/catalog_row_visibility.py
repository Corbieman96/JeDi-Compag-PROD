from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from catalogs.catalog_nav_registry import (
    SLUG_CONTAINER_PASSPORT,
    SLUG_OFFLINE_ADDRESSES,
    SLUG_PASPORT_STREDISKO,
)
from users.models import UserAccessProfile
from users.services.access_profile import get_access_profile
from users.services.nav_visibility import (
    effective_show_address_data_nav,
    effective_show_catalogs_nav,
)


def _override_for_slug(profile: UserAccessProfile | None, slug: str) -> str:
    raw = {}
    if profile and isinstance(profile.catalog_item_nav, dict):
        raw = profile.catalog_item_nav
    val = raw.get(slug)
    if val in (UserAccessProfile.NavOverride.SHOW, UserAccessProfile.NavOverride.HIDE, UserAccessProfile.NavOverride.INHERIT):
        return val
    return UserAccessProfile.NavOverride.INHERIT


# Řádky viditelné jen po výslovném SHOW v profilu (INHERIT = skryto).
_CATALOG_INDEX_ROW_OPT_IN_SLUGS = frozenset({SLUG_CONTAINER_PASSPORT})


def effective_show_catalog_index_row(user: AbstractBaseUser, slug: str) -> bool:
    """Viditelnost jednoho řádku v přehledu /catalogs/ (kromě kombinace s modulem adres — viz níže)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not effective_show_catalogs_nav(user):
        return False
    prof = get_access_profile(user)
    if slug == SLUG_PASPORT_STREDISKO:
        mode = _override_for_slug(prof, slug)
        if mode == UserAccessProfile.NavOverride.HIDE:
            return False
        if mode == UserAccessProfile.NavOverride.SHOW:
            return True
        return effective_show_catalog_index_row(user, SLUG_CONTAINER_PASSPORT)
    mode = _override_for_slug(prof, slug)
    if mode == UserAccessProfile.NavOverride.HIDE:
        return False
    if mode == UserAccessProfile.NavOverride.SHOW:
        return True
    if slug in _CATALOG_INDEX_ROW_OPT_IN_SLUGS:
        return False
    return True


def effective_show_offline_addresses_catalog_row(user: AbstractBaseUser) -> bool:
    """Řádek offline adres v číselnících: potřeba přístup k adresám + řádek nesmí být skrytý."""
    if not effective_show_address_data_nav(user):
        return False
    return effective_show_catalog_index_row(user, SLUG_OFFLINE_ADDRESSES)
