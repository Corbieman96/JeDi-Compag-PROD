"""
Viditelnost funkcí a dat podle aplikační role (skupina Django + Admin = superuser).

Úpravy přístupů dělejte zde — šablony používají `role_access` z context processoru,
v pohledech importujte funkce z tohoto modulu místo rozptýlených `is_superuser`.
"""

from __future__ import annotations

from types import SimpleNamespace

from catalogs.models import DriverProfile
from users.constants import (
    ROLE_ADMIN,
    ROLE_DISPECER,
    ROLE_KONTROLOR,
    ROLE_RIDIC,
    ROLE_SBERNY_DVUR,
    ROLE_ZADAVATEL,
)
from users.services.nav_visibility import (
    effective_show_customer_requests_nav,
    effective_show_invoice_queue_nav,
    effective_show_address_data_nav,
    effective_show_catalogs_nav,
    effective_show_dashboard_nav,
    effective_show_pruvodky_nav,
    effective_show_reports_nav,
    effective_show_settings_nav,
)
from users.services.access_profile import get_access_profile
from users.services.roles import get_user_role_label


def _driver_identity_line(user, profile, is_ridic: bool) -> str:
    """Řádek do horní lišty: příjmení jméno a osobní číslo z DriverProfile, ne technický login."""
    if not is_ridic:
        return ""
    if not profile.driver_profile_id:
        return user.username
    d = (
        DriverProfile.objects.filter(pk=profile.driver_profile_id)
        .only("first_name", "last_name", "personal_number")
        .first()
    )
    if not d:
        return user.username
    parts = [(d.last_name or "").strip(), (d.first_name or "").strip()]
    name = " ".join(p for p in parts if p).strip()
    if not name:
        name = d.personal_number
    return f"{name} ({d.personal_number})"


def app_role(user) -> str:
    """Aktuální role z číselníku skupin; superuser se mapuje na Admin."""
    if not user.is_authenticated:
        return ""
    return get_user_role_label(user)


def can_see_all_waste_docs(user) -> bool:
    """Admin a Dispečer vidí všechny průvodky / jízdy; ostatní jen vlastní."""
    if not user.is_authenticated:
        return False
    return app_role(user) in (ROLE_ADMIN, ROLE_DISPECER)


def can_manage_users(user) -> bool:
    """Správa uživatelů — pouze Admin."""
    return user.is_authenticated and user.is_superuser


def can_access_app_settings(user) -> bool:
    """Stránka Nastavení aplikace."""
    return user.is_authenticated and user.is_superuser


def can_access_offline_addresses(user) -> bool:
    """Modul offline adres."""
    return user.is_authenticated and user.is_superuser


def can_edit_catalog_records(user) -> bool:
    """Úpravy záznamů v číselnících (CRUD) — výchozí stejné jako dříve jen superuser."""
    return user.is_authenticated and user.is_superuser


def can_manage_dashboard_notes(user) -> bool:
    """Denní poznámky na dashboardu (vytvoření, úprava, mazání, promazání). Superuser vždy smí."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return bool(get_access_profile(user).can_manage_dashboard_notes)


def can_manage_driver_absences(user) -> bool:
    """Nepřítomnosti řidičů z dashboardu — Admin a Dispečer."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return app_role(user) in (ROLE_ADMIN, ROLE_DISPECER)


def can_export_name_subject_pio_profile(user) -> bool:
    """Export předvyplněné šablony PIO z úpravy subjektu F/P — superuser vždy; ostatní dědí z role."""
    from users.models import UserAccessProfile
    from users.services.role_permissions import role_default_export_pio_profile

    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    prof = get_access_profile(user)
    mode = prof.export_pio_profile
    if mode == UserAccessProfile.NavOverride.SHOW:
        return True
    if mode == UserAccessProfile.NavOverride.HIDE:
        return False
    return role_default_export_pio_profile(get_user_role_label(user))


def build_role_access_context(user) -> SimpleNamespace:
    """Hodnoty pro šablony (topbar, podmíněné bloky)."""
    if not user.is_authenticated:
        return SimpleNamespace(
            role_label="",
            is_admin=False,
            show_users_nav=False,
            show_dashboard_nav=False,
            show_pruvodky_nav=False,
            show_customer_requests_nav=False,
            show_invoice_queue_nav=False,
            show_catalogs_nav=False,
            show_settings_nav=False,
            show_address_data_nav=False,
            show_reports_nav=False,
            can_delete_all_pruvodky=False,
            can_see_all_waste_docs=False,
            can_create_pruvodka=False,
            can_manage_dashboard_notes=False,
            can_manage_driver_absences=False,
            can_export_name_subject_pio_profile=False,
            is_sberny_dvur=False,
            is_ridic=False,
            show_driver_portal_nav=False,
            driver_portal_linked=False,
            driver_identity_line="",
        )
    role = app_role(user)
    is_admin = user.is_superuser
    see_all = can_see_all_waste_docs(user)
    profile = get_access_profile(user)
    can_delete_all = bool(is_admin and profile.can_delete_all_pruvodky)
    is_ridic = role == ROLE_RIDIC
    driver_linked = bool(profile.driver_profile_id)
    driver_identity_line = _driver_identity_line(user, profile, is_ridic)
    from users.services.waste_doc_permissions import can_create_pruvodka

    return SimpleNamespace(
        role_label=role,
        is_admin=is_admin,
        show_users_nav=can_manage_users(user),
        show_dashboard_nav=effective_show_dashboard_nav(user),
        show_pruvodky_nav=effective_show_pruvodky_nav(user),
        show_customer_requests_nav=effective_show_customer_requests_nav(user),
        show_invoice_queue_nav=effective_show_invoice_queue_nav(user),
        show_catalogs_nav=effective_show_catalogs_nav(user),
        show_settings_nav=effective_show_settings_nav(user),
        show_address_data_nav=effective_show_address_data_nav(user),
        show_reports_nav=effective_show_reports_nav(user),
        can_delete_all_pruvodky=can_delete_all,
        can_see_all_waste_docs=see_all,
        can_create_pruvodka=can_create_pruvodka(user),
        can_manage_dashboard_notes=can_manage_dashboard_notes(user),
        can_manage_driver_absences=can_manage_driver_absences(user),
        can_export_name_subject_pio_profile=can_export_name_subject_pio_profile(user),
        # Kontrolor / Zadavatel — vlastní průvodky; šablony mohou rozšiřovat:
        is_dispecer=role == ROLE_DISPECER,
        is_zadavatel=role == ROLE_ZADAVATEL,
        is_kontrolor=role == ROLE_KONTROLOR,
        is_sberny_dvur=role == ROLE_SBERNY_DVUR,
        is_ridic=is_ridic,
        show_driver_portal_nav=is_ridic,
        driver_portal_linked=driver_linked,
        driver_identity_line=driver_identity_line,
    )
