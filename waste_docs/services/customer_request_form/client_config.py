"""Konfigurace pro JS formuláře zákaznického požadavku."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.urls import reverse

from catalogs.catalog_nav_registry import SLUG_CUSTOMER_REQUEST_TEMPLATES
from users.services.catalog_row_visibility import effective_show_catalog_index_row
from waste_docs.services.customer_request_date_closure import (
    is_target_date_closed,
    target_date_min_for_user,
)


def _name_subject_pairs_modal_url_template() -> str:
    return reverse("catalogs:name_pairs_modal", args=[0]).replace("/0/", "/__PROFILE_PK__/")


def customer_request_form_client_config(
    *,
    can_edit_name_subject_pairs: bool,
    submit_user: AbstractBaseUser | None = None,
    initial_subject_snapshot: dict | None = None,
) -> dict:
    min_date = target_date_min_for_user(submit_user)
    today_closed = False
    if submit_user and min_date is not None:
        from django.utils import timezone

        today_closed = is_target_date_closed(timezone.localdate())
    config = {
        "canEditNameSubjectPairs": can_edit_name_subject_pairs,
        "subjectPairsButtonId": "customer-request-edit-subject-pairs-btn",
        "targetDateMin": min_date.isoformat() if min_date else None,
        "todayClosed": today_closed,
        "urls": {
            "nameSubjectPairsModal": _name_subject_pairs_modal_url_template(),
            "subjectProfileByName": reverse("waste_docs:subject_profile_by_name"),
            "subjectSearch": reverse("waste_docs:subject_search"),
            "kindClosureStatus": reverse("waste_docs:customer_request_kind_closure_status"),
        },
        "zpoPairing": {
            "endpoint": reverse("waste_docs:zpo_pairing_draft"),
            "fieldMap": [
                ["name_id", "id_name_existing"],
                ["waste_type_id", "id_waste_type"],
                ["suffix_id", "id_suffix"],
                ["activity_id", "id_activity"],
                ["drive_date", "id_target_date"],
                ["contact_phone", "id_contact_phone"],
                ["contact_note", "id_contact_note"],
                ["fulfillment_address_value", "id_address_value"],
                ["facility_address_display", "id_facility_address_value"],
            ],
            "watchElementIds": [
                "id_name_existing",
                "id_name_lookup",
                "id_waste_type",
                "customer-request-waste-combo",
                "id_suffix",
                "id_activity",
                "id_target_date",
                "id_contact_phone",
                "id_contact_note",
                "id_address_value",
                "id_facility_address_value",
            ],
        },
    }
    templates_enabled = bool(
        submit_user
        and submit_user.is_authenticated
        and effective_show_catalog_index_row(submit_user, SLUG_CUSTOMER_REQUEST_TEMPLATES)
    )
    config["customerRequestTemplates"] = {
        "enabled": templates_enabled,
        "listUrl": reverse("customer_request_templates:api_list"),
        "saveUrl": reverse("customer_request_templates:api_save"),
    }
    if initial_subject_snapshot:
        config["initialSubjectSnapshot"] = initial_subject_snapshot
    return config
