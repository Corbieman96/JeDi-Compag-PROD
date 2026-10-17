from .access import (
    build_role_access_context,
    can_access_app_settings,
    can_access_offline_addresses,
    can_edit_catalog_records,
    can_manage_dashboard_notes,
    can_manage_driver_absences,
    can_manage_users,
    can_see_all_waste_docs,
)
from .nav_visibility import (
    effective_show_customer_requests_nav,
    effective_show_invoice_queue_nav,
    effective_show_address_data_nav,
    effective_show_catalogs_nav,
    effective_show_settings_nav,
)
from .roles import ensure_role_groups, get_user_role_label, set_user_role
from .waste_doc_permissions import can_edit_existing_pruvodka
