from .activity import activity_create, activity_delete, activity_edit, activity_list
from .drivers import (
    driver_availability_note_quick_clear,
    driver_availability_note_quick_update,
    driver_absence_delete,
    driver_absence_edit,
    driver_absence_quick_add,
    driver_absence_quick_delete,
    driver_absence_quick_update,
    driver_create,
    driver_delete,
    driver_edit,
    driver_list,
    driver_portal_invite_create,
    driver_portal_invite_set_status,
    driver_portal_unlink_linked_user,
)
from .pasport_stredisko import (
    pasport_stredisko_create,
    pasport_stredisko_delete,
    pasport_stredisko_edit,
    pasport_stredisko_list,
)
from .container_passport import (
    container_passport_create,
    container_passport_delete,
    container_passport_edit,
    container_passport_history,
    container_passport_list,
)
from .generic import catalog_create, catalog_delete, catalog_edit, catalog_index, catalog_list
from .name_subject import (
    address_admin_units,
    address_geocode,
    address_reverse_geocode,
    address_suggestions,
    ares_lookup,
    name_subject_create,
    name_subject_delete,
    name_subject_edit,
    name_subject_list,
    name_subject_user_pio_download,
    name_subject_user_pio_download_draft,
)
from .name_subject_pairs_modal import name_subject_pairs_modal
from .suffix_site import (
    suffix_address_geocode,
    suffix_address_reverse_geocode,
    suffix_address_suggestions,
    suffix_site_create,
    suffix_site_delete,
    suffix_site_edit,
    suffix_site_list,
    visoh2_lookup,
)
from .waste_type import (
    waste_type_create,
    waste_type_delete,
    waste_type_edit,
    waste_type_import,
    waste_type_list,
)
from .vehicle_rz import (
    vehicle_kind_create,
    vehicle_kind_create_ajax,
    vehicle_kind_delete,
    vehicle_kind_edit,
    vehicle_kind_list,
    vehicle_kind_reorder,
    vehicle_rz_create,
    vehicle_rz_delete,
    vehicle_rz_edit,
    vehicle_rz_list,
)
from .vehicle_repairs import (
    vehicle_rz_repair_create,
    vehicle_rz_repair_delete,
    vehicle_rz_repair_edit,
    vehicle_rz_repair_list,
)
