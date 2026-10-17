from django.urls import path

from .views.ajax import (
    activity_field_rules_json,
    address_geocode,
    address_reverse_geocode,
    address_suggestions,
    drivers_by_context,
    follow_up_candidates_json,
    subject_open_follow_ups_json,
    subject_profile_id_by_name,
    subject_search,
    suffixes_by_context,
    vehicle_rz_by_activity,
)
from .views.blank_pruvodka import (
    blank_pruvodka_archive,
    blank_pruvodka_archive_bulk,
    blank_pruvodka_create,
    blank_pruvodka_merged_print_pdf,
    blank_pruvodka_print,
)
from .customer_request_kind_closure.views import (
    customer_request_kind_closure_status,
    customer_request_kind_closure_toggle,
)
from .customer_request_pair_ride_note.views import customer_request_pair_ride_note
from .views.customer_requests import (
    customer_request_create,
    customer_request_create_name_ajax,
    customer_request_closure_toggle,
    customer_request_dispatch_withdraw,
    customer_request_detail,
    customer_request_dispatcher_review,
    customer_request_form_delete,
    customer_request_form_edit,
    customer_request_invoice_queue,
    customer_request_invoice_review,
    customer_request_day_kind_counts_json,
    customer_request_list,
    customer_request_set_follow_up_date,
    customer_request_submitter_update,
)
from .views.dashboard_bulk import (
    dashboard_bulk_delete_protocol,
    dashboard_bulk_generate,
    dashboard_bulk_generate_protocol,
    dashboard_bulk_print,
)
from .views.dashboard_day_purge import dashboard_day_purge, dashboard_media_purge_all
from .views.dispatch import (
    svoz_dispatch_plan,
    svoz_matrix_validate_container,
    svoz_request_create,
    svoz_submit_error_log,
    svoz_submit_error_log_acknowledge,
    svoz_submit_error_log_delete_row,
    svoz_submit_error_log_delete_selected,
    svoz_submit_error_log_delete_yard,
    svoz_submit_error_log_modal_partial,
    svoz_submit_error_log_txt,
    svoz_task_quick_edit,
    yard_ride_create,
    yard_ride_validate_container,
)
from .views.print_file_pdf import print_file_as_pdf
from .views.media_download import media_download
from .views.protocol_media_pdf import protocol_media_pdf
from .views.print_bundle_prepare import (
    blank_pruvodka_print_prepare,
    dashboard_bulk_print_prepare,
    ride_print_bundle_prepare,
    yard_print_created_prepare,
)
from .views.ride_print_bundle_protocol import (
    ride_print_bundle_delete_protocol,
    ride_print_bundle_generate_protocol,
)
from .views.print_file_mark import mark_file_row_printed
from .views.print_merged_bulk import bulk_merged_print_pdf, bulk_merged_print_pdf_download
from .views.pruvodka_edit import pruvodka_edit
from .views.pruvodka_pages import (
    pruvodka_archive,
    pruvodka_create,
    pruvodka_delete_all,
    pruvodka_detail,
    pruvodka_download,
    pruvodka_follow_up_close,
    pruvodka_generate,
    pruvodka_list,
    pruvodka_list_export_xlsx,
    pruvodka_zpo_preview,
    ride_attachment_print_pdf,
    ride_pruvodka_pdf,
    ride_print_bundle,
    yard_print_created,
)
from .views.ride_protocol import (
    ride_protocol_day_xlsx,
    ride_protocol_group_pdf,
    ride_protocol_group_xlsx,
    ride_protocol_single_pdf,
    ride_protocol_single_xlsx,
)
from .views.ride_soft_delete import ride_soft_delete_confirm, ride_soft_delete_log_list
from .views.ride_templates import (
    ride_template_create_from_pruvodka,
    ride_template_delete,
    ride_template_edit,
    ride_template_list,
    ride_templates_by_vehicle_kind,
)
from .views.yard_hub import yard_hub
from .views.zpo_pairing import zpo_pairing_draft_json
from .views.ride_document_email import (
    ride_email_recipient_add,
    ride_email_recipient_delete,
    ride_email_recipients_list,
    ride_group_email_cancel,
    ride_group_email_prepare,
)
from .views.ride_reassign_driver import ride_reassign_driver

app_name = "waste_docs"

urlpatterns = [
    path("deleted/", ride_soft_delete_log_list, name="ride_soft_delete_log_list"),
    path("", pruvodka_list, name="list"),
    path("list/jizdy.xlsx", pruvodka_list_export_xlsx, name="list_jizdy_xlsx"),
    path("delete-all/", pruvodka_delete_all, name="delete_all"),
    path("new/", pruvodka_create, name="create"),
    path("templates/", ride_template_list, name="ride_template_list"),
    path("templates/<int:pk>/edit/", ride_template_edit, name="ride_template_edit"),
    path("templates/<int:pk>/delete/", ride_template_delete, name="ride_template_delete"),
    path("bianko/create/", blank_pruvodka_create, name="blank_pruvodka_create"),
    path("bianko/print/", blank_pruvodka_print, name="blank_pruvodka_print"),
    path("bianko/print/prepare/", blank_pruvodka_print_prepare, name="blank_pruvodka_print_prepare"),
    path("bianko/print/merged-pdf/", blank_pruvodka_merged_print_pdf, name="blank_pruvodka_merged_print_pdf"),
    path("bianko/archive-bulk/", blank_pruvodka_archive_bulk, name="blank_pruvodka_archive_bulk"),
    path("bianko/<int:pk>/archive/", blank_pruvodka_archive, name="blank_pruvodka_archive"),
    path("sberny-dvur/", yard_hub, name="yard_hub"),
    path("sberny-dvur/nova-jizda/", yard_ride_create, name="yard_ride_create"),
    path(
        "sberny-dvur/nova-jizda/validate-container/",
        yard_ride_validate_container,
        name="yard_ride_validate_container",
    ),
    path("svoz-task/<int:pk>/quick-edit/", svoz_task_quick_edit, name="svoz_task_quick_edit"),
    path("svoz-pozadavek/", svoz_request_create, name="svoz_request"),
    path(
        "svoz-pozadavek/validate-container/",
        svoz_matrix_validate_container,
        name="svoz_matrix_validate_container",
    ),
    path("svoz-error-log/", svoz_submit_error_log, name="svoz_submit_error_log"),
    path(
        "svoz-error-log/modal-partial/",
        svoz_submit_error_log_modal_partial,
        name="svoz_submit_error_log_modal_partial",
    ),
    path(
        "svoz-error-log/<int:pk>/delete/",
        svoz_submit_error_log_delete_row,
        name="svoz_submit_error_log_delete_row",
    ),
    path(
        "svoz-error-log/yard/<int:subject_pk>/delete/",
        svoz_submit_error_log_delete_yard,
        name="svoz_submit_error_log_delete_yard",
    ),
    path(
        "svoz-error-log/yard/<int:subject_pk>/delete-selected/",
        svoz_submit_error_log_delete_selected,
        name="svoz_submit_error_log_delete_selected",
    ),
    path(
        "svoz-error-log/acknowledge/",
        svoz_submit_error_log_acknowledge,
        name="svoz_submit_error_log_acknowledge",
    ),
    path(
        "svoz-error-log/yard/<int:subject_pk>.txt",
        svoz_submit_error_log_txt,
        name="svoz_submit_error_log_txt",
    ),
    path("customer-requests/", customer_request_list, name="customer_request_list"),
    path(
        "customer-requests/<int:pk>/day-kind-counts/",
        customer_request_day_kind_counts_json,
        name="customer_request_day_kind_counts",
    ),
    path("customer-requests/new/", customer_request_create, name="customer_request_create"),
    path(
        "customer-requests/closure-toggle/",
        customer_request_closure_toggle,
        name="customer_request_closure_toggle",
    ),
    path(
        "customer-requests/kind-closure-toggle/",
        customer_request_kind_closure_toggle,
        name="customer_request_kind_closure_toggle",
    ),
    path(
        "customer-requests/kind-closure-status/",
        customer_request_kind_closure_status,
        name="customer_request_kind_closure_status",
    ),
    path(
        "customer-requests/<int:pk>/dispatch-withdraw/",
        customer_request_dispatch_withdraw,
        name="customer_request_dispatch_withdraw",
    ),
    path(
        "customer-requests/invoice-queue/",
        customer_request_invoice_queue,
        name="customer_request_invoice_queue",
    ),
    path(
        "customer-requests/name-create/",
        customer_request_create_name_ajax,
        name="customer_request_create_name_ajax",
    ),
    path(
        "customer-requests/pair-ride-note/",
        customer_request_pair_ride_note,
        name="customer_request_pair_ride_note",
    ),
    path("customer-requests/<int:pk>/", customer_request_detail, name="customer_request_detail"),
    path(
        "customer-requests/<int:pk>/edit/",
        customer_request_form_edit,
        name="customer_request_form_edit",
    ),
    path(
        "customer-requests/<int:pk>/delete/",
        customer_request_form_delete,
        name="customer_request_form_delete",
    ),
    path(
        "customer-requests/<int:pk>/submitter-update/",
        customer_request_submitter_update,
        name="customer_request_submitter_update",
    ),
    path(
        "customer-requests/<int:pk>/invoice-review/",
        customer_request_invoice_review,
        name="customer_request_invoice_review",
    ),
    path(
        "customer-requests/<int:pk>/dispatcher-review/",
        customer_request_dispatcher_review,
        name="customer_request_dispatcher_review",
    ),
    path(
        "customer-requests/<int:pk>/follow-up-date/",
        customer_request_set_follow_up_date,
        name="customer_request_set_follow_up_date",
    ),
    path("svoz-plan/", svoz_dispatch_plan, name="svoz_dispatch_plan"),
    path("new/subject-search/", subject_search, name="subject_search"),
    path("new/subject-profile-by-name/", subject_profile_id_by_name, name="subject_profile_by_name"),
    path("new/vehicle-rz-by-activity/", vehicle_rz_by_activity, name="vehicle_rz_by_activity"),
    path("new/drivers-by-context/", drivers_by_context, name="drivers_by_context"),
    path("new/ride-templates-by-vehicle-kind/", ride_templates_by_vehicle_kind, name="ride_templates_by_vehicle_kind"),
    path("new/address-suggestions/", address_suggestions, name="address_suggestions"),
    path("new/address-geocode/", address_geocode, name="address_geocode"),
    path("new/address-reverse-geocode/", address_reverse_geocode, name="address_reverse_geocode"),
    path("new/suffixes-by-context/", suffixes_by_context, name="suffixes_by_context"),
    path("new/activity-field-rules/", activity_field_rules_json, name="activity_field_rules"),
    path("new/follow-up-candidates/", follow_up_candidates_json, name="follow_up_candidates"),
    path(
        "new/subject-open-follow-ups/",
        subject_open_follow_ups_json,
        name="subject_open_follow_ups",
    ),
    path("new/zpo-pairing-draft/", zpo_pairing_draft_json, name="zpo_pairing_draft"),
    path("<int:pk>/edit/", pruvodka_edit, name="edit"),
    path("<int:pk>/", pruvodka_detail, name="detail"),
    path("<int:pk>/follow-up/close/", pruvodka_follow_up_close, name="follow_up_close"),
    path("<int:pk>/generate/", pruvodka_generate, name="generate"),
    path("<int:pk>/download/", pruvodka_download, name="download"),
    path(
        "<int:pk>/attachments/<int:att_pk>/print.pdf",
        ride_attachment_print_pdf,
        name="ride_attachment_print_pdf",
    ),
    path("<int:pk>/pruvodka.pdf", ride_pruvodka_pdf, name="ride_pruvodka_pdf"),
    path("<int:pk>/soft-delete/", ride_soft_delete_confirm, name="ride_soft_delete_confirm"),
    path("<int:pk>/archive/", pruvodka_archive, name="archive"),
    path("<int:pk>/protocol-xlsx/", ride_protocol_single_xlsx, name="ride_protocol_single_xlsx"),
    path("<int:pk>/protocol.pdf", ride_protocol_single_pdf, name="ride_protocol_single_pdf"),
    path("<int:pk>/zpo-preview/", pruvodka_zpo_preview, name="zpo_preview"),
    path("<int:pk>/create-template/", ride_template_create_from_pruvodka, name="ride_template_create_from_pruvodka"),
    path("print/as-pdf/", print_file_as_pdf, name="print_file_as_pdf"),
    path("print/media-file/", media_download, name="media_download"),
    path("print/protocol-media.pdf", protocol_media_pdf, name="protocol_media_pdf"),
    path("print/mark-printed/", mark_file_row_printed, name="mark_file_row_printed"),
    path("print/yard-created/", yard_print_created, name="yard_print_created"),
    path("print/yard-created/prepare/", yard_print_created_prepare, name="yard_print_created_prepare"),
    path("print/ride-bundle/", ride_print_bundle, name="ride_print_bundle"),
    path("print/ride-bundle/prepare/", ride_print_bundle_prepare, name="ride_print_bundle_prepare"),
    path(
        "print/ride-bundle/generate-protocol/",
        ride_print_bundle_generate_protocol,
        name="ride_print_bundle_generate_protocol",
    ),
    path(
        "print/ride-bundle/delete-protocol/",
        ride_print_bundle_delete_protocol,
        name="ride_print_bundle_delete_protocol",
    ),
    path("print/ride-protocol-day/", ride_protocol_day_xlsx, name="ride_protocol_day_xlsx"),
    path("print/ride-protocol/", ride_protocol_group_xlsx, name="ride_protocol_group_xlsx"),
    path("print/ride-protocol.pdf", ride_protocol_group_pdf, name="ride_protocol_group_pdf"),
    path("print/bulk-merged-pdf/", bulk_merged_print_pdf, name="bulk_merged_print_pdf"),
    path(
        "print/bulk-merged-pdf/<str:name>",
        bulk_merged_print_pdf_download,
        name="bulk_merged_print_download",
    ),
    path("print/dashboard-bulk/", dashboard_bulk_print, name="dashboard_bulk_print"),
    path("print/dashboard-bulk/prepare/", dashboard_bulk_print_prepare, name="dashboard_bulk_print_prepare"),
    path("print/dashboard-bulk/generate-protocol/", dashboard_bulk_generate_protocol, name="dashboard_bulk_generate_protocol"),
    path("print/dashboard-bulk/delete-protocol/", dashboard_bulk_delete_protocol, name="dashboard_bulk_delete_protocol"),
    path("dashboard/bulk-generate/", dashboard_bulk_generate, name="dashboard_bulk_generate"),
    path("dashboard/purge-generated/", dashboard_day_purge, name="dashboard_day_purge"),
    path("dashboard/purge-generated-all/", dashboard_media_purge_all, name="dashboard_media_purge_all"),
    path("email-dispatch/group/prepare/", ride_group_email_prepare, name="ride_group_email_prepare"),
    path("email-dispatch/group/cancel/", ride_group_email_cancel, name="ride_group_email_cancel"),
    path("reassign-driver/", ride_reassign_driver, name="ride_reassign_driver"),
    path("email-dispatch/recipients/", ride_email_recipients_list, name="ride_email_recipients_list"),
    path("email-dispatch/recipients/add/", ride_email_recipient_add, name="ride_email_recipient_add"),
    path(
        "email-dispatch/recipients/<int:pk>/delete/",
        ride_email_recipient_delete,
        name="ride_email_recipient_delete",
    ),
]
