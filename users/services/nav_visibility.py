from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from core.models import AppSettings
from users.constants import ROLE_CHOICES, ROLE_DISPECER, ROLE_RIDIC, ROLE_ZADAVATEL
from users.models import UserAccessProfile
from users.services.access_profile import get_access_profile
from users.services.roles import get_user_role_label

# Klíče musí odpovídat polím v Nastavení aplikace (globální matice rolí × menu).
ROLE_NAV_FLAG_KEYS: tuple[str, ...] = (
    "dashboard",
    "pruvodky",
    "customer_requests",
    "invoice_queue",
    "catalogs",
    "settings",
    "address_data",
    "reports",
)

ROLE_NAV_LABELS_CZ: dict[str, str] = {
    "dashboard": "Dashboard",
    "pruvodky": "Jízdy",
    "customer_requests": "Požadavky",
    "invoice_queue": "Schvalování záloh",
    "catalogs": "Číselníky",
    "settings": "Nastavení",
    "address_data": "Adresy (offline)",
    "reports": "Reporty",
}


def fallback_role_nav_matrix() -> dict[str, dict[str, bool]]:
    """Výchozí chování jako dříve (před globálním nastavením v AppSettings)."""
    common = {
        "dashboard": True,
        "pruvodky": True,
        "customer_requests": True,
        "invoice_queue": False,
        "catalogs": True,
        "settings": False,
        "address_data": False,
        "reports": False,
    }
    out = {role: dict(common) for role, _ in ROLE_CHOICES}
    out[ROLE_ZADAVATEL] = {**common, "pruvodky": False}
    out[ROLE_RIDIC] = {
        "dashboard": False,
        "pruvodky": False,
        "customer_requests": False,
        "invoice_queue": False,
        "catalogs": False,
        "settings": False,
        "address_data": False,
        "reports": False,
    }
    return out


def merged_role_nav_matrix(stored: dict | None = None) -> dict[str, dict[str, bool]]:
    """Sloučí záznam z DB s výchozí maticí (doplní chybějící role/klíče)."""
    base = fallback_role_nav_matrix()
    if not stored:
        return base
    for role, row in stored.items():
        if role not in base or not isinstance(row, dict):
            continue
        for k, v in row.items():
            if k in ROLE_NAV_FLAG_KEYS and isinstance(v, bool):
                base[role][k] = v
    return base


def _matrix_from_db() -> dict[str, dict[str, bool]]:
    try:
        raw = AppSettings.load().role_nav_defaults or {}
    except Exception:
        raw = {}
    return merged_role_nav_matrix(raw if isinstance(raw, dict) else {})


def _inherit_nav_flag(user: AbstractBaseUser, flag: str) -> bool:
    assert flag in ROLE_NAV_FLAG_KEYS
    role = get_user_role_label(user)
    matrix = _matrix_from_db()
    if role in matrix:
        return bool(matrix[role].get(flag))
    return bool(matrix.get(ROLE_DISPECER, {}).get(flag))


def effective_show_dashboard_nav(user: AbstractBaseUser) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    prof = get_access_profile(user)
    if prof.nav_dashboard == UserAccessProfile.NavOverride.HIDE:
        return False
    if prof.nav_dashboard == UserAccessProfile.NavOverride.SHOW:
        return True
    return _inherit_nav_flag(user, "dashboard")


def effective_show_pruvodky_nav(user: AbstractBaseUser) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    prof = get_access_profile(user)
    if prof.nav_pruvodky == UserAccessProfile.NavOverride.HIDE:
        return False
    if prof.nav_pruvodky == UserAccessProfile.NavOverride.SHOW:
        return True
    return _inherit_nav_flag(user, "pruvodky")


def effective_show_customer_requests_nav(user: AbstractBaseUser) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    prof = get_access_profile(user)
    if prof.nav_customer_requests == UserAccessProfile.NavOverride.HIDE:
        return False
    if prof.nav_customer_requests == UserAccessProfile.NavOverride.SHOW:
        return True
    return _inherit_nav_flag(user, "customer_requests")


def effective_show_invoice_queue_nav(user: AbstractBaseUser) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    prof = get_access_profile(user)
    if prof.nav_invoice_queue == UserAccessProfile.NavOverride.HIDE:
        return False
    if prof.nav_invoice_queue == UserAccessProfile.NavOverride.SHOW:
        return True
    return _inherit_nav_flag(user, "invoice_queue")


def effective_show_catalogs_nav(user: AbstractBaseUser) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    prof = get_access_profile(user)
    if prof.nav_catalogs == UserAccessProfile.NavOverride.HIDE:
        return False
    if prof.nav_catalogs == UserAccessProfile.NavOverride.SHOW:
        return True
    return _inherit_nav_flag(user, "catalogs")


def effective_show_settings_nav(user: AbstractBaseUser) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    prof = get_access_profile(user)
    if prof.nav_settings == UserAccessProfile.NavOverride.HIDE:
        return False
    if prof.nav_settings == UserAccessProfile.NavOverride.SHOW:
        return True
    return _inherit_nav_flag(user, "settings")


def effective_show_address_data_nav(user: AbstractBaseUser) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    prof = get_access_profile(user)
    if prof.nav_address_data == UserAccessProfile.NavOverride.HIDE:
        return False
    if prof.nav_address_data == UserAccessProfile.NavOverride.SHOW:
        return True
    return _inherit_nav_flag(user, "address_data")


def effective_show_reports_nav(user: AbstractBaseUser) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    prof = get_access_profile(user)
    if prof.nav_reports == UserAccessProfile.NavOverride.HIDE:
        return False
    if prof.nav_reports == UserAccessProfile.NavOverride.SHOW:
        return True
    return _inherit_nav_flag(user, "reports")
