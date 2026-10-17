from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from users.constants import ROLE_ADMIN, ROLE_DISPECER, ROLE_ZADAVATEL
from users.services.nav_visibility import effective_show_pruvodky_nav
from users.services.roles import get_user_role_label
from users.services.sberny_dvur import can_create_svoz_request
from users.services.access import can_see_all_waste_docs
from users.services.access_profile import get_access_profile


def can_access_waste_docs_list(user: AbstractBaseUser) -> bool:
    """Seznam jízd /waste-docs/ a read-only detail — stejná podmínka jako menu Jízdy."""
    return effective_show_pruvodky_nav(user)


def can_access_pruvodka_files(user: AbstractBaseUser) -> bool:
    """Stáhnout / PDF průvodky — seznam jízd nebo založení ze sběrného dvora."""
    return bool(can_access_waste_docs_list(user) or can_create_pruvodka(user))


def can_see_all_rides_in_list(user: AbstractBaseUser) -> bool:
    """Seznam jízd: každý s přístupem k modulu Jízdy vidí všechny řádky."""
    return can_access_waste_docs_list(user)


def can_view_pruvodka(user: AbstractBaseUser, item) -> bool:
    """Detail / náhled konkrétní jízdy (bez nutnosti oprávnění k úpravě)."""
    if not user.is_authenticated:
        return False
    if can_see_all_rides_in_list(user):
        return True
    return item.created_by_id == user.id


def can_create_pruvodka_dashboard(user: AbstractBaseUser) -> bool:
    """Ikona / odkaz „Nová jízda“ na dashboardu v panelu Seznam jízd — Admin nebo Dispečer + profil."""
    if not can_create_pruvodka(user):
        return False
    if user.is_superuser:
        return True
    role = get_user_role_label(user)
    return role in (ROLE_ADMIN, ROLE_DISPECER)


def can_create_pruvodka(user: AbstractBaseUser) -> bool:
    """Založení nové jízdy: profil, viditelnost modulu Jízdy nebo režim sběrného dvora."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role = get_user_role_label(user)
    prof = get_access_profile(user)
    if role == ROLE_ZADAVATEL:
        return False
    if not prof.can_create_pruvodka:
        return False
    return bool(effective_show_pruvodky_nav(user) or can_create_svoz_request(user))


def can_edit_existing_pruvodka(user: AbstractBaseUser, item) -> bool:
    """Úprava uložené průvodky: superuser vždy; jinak podle profilu a viditelnosti záznamu."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    prof = get_access_profile(user)
    if not prof.can_edit_existing_pruvodka:
        return False
    if can_see_all_waste_docs(user):
        return True
    return item.created_by_id == user.id


def can_delete_all_pruvodky(user: AbstractBaseUser) -> bool:
    """Hromadné mazání všech průvodek: jen admin + explicitní povolení v profilu."""
    if not user.is_authenticated or not user.is_superuser:
        return False
    prof = get_access_profile(user)
    return bool(prof.can_delete_all_pruvodky)


def can_archive_pruvodka(user: AbstractBaseUser) -> bool:
    """Archivace jedné jízdy: admin nebo uživatel s explicitním povolením v profilu."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    prof = get_access_profile(user)
    return bool(prof.can_delete_all_pruvodky)


def can_purge_dashboard_day_files(user: AbstractBaseUser) -> bool:
    """Koš v panelu Seznam jízd — smazání vygenerovaných souborů za den (jen Admin)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_user_role_label(user) == ROLE_ADMIN
