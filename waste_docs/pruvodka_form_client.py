"""Konfigurace pro statický JS formuláře nové průvodky (URL + data z Django)."""

from __future__ import annotations

from django.urls import reverse


def _name_subject_pairs_modal_url_template() -> str:
    return reverse("catalogs:name_pairs_modal", args=[0]).replace("/0/", "/__PROFILE_PK__/")


def pruvodka_create_form_client_config(
    *,
    waste_type_meta: dict,
    default_city: str,
    default_map_lat,
    default_map_lng,
    yard_standalone: dict | None = None,
    can_edit_name_subject_pairs: bool = False,
    initial_subject_profile_id: int | None = None,
) -> dict:
    return {
        "wasteTypeMeta": waste_type_meta,
        "defaultCity": default_city,
        "defaultMapLat": str(default_map_lat) if default_map_lat is not None else "49.8175",
        "defaultMapLng": str(default_map_lng) if default_map_lng is not None else "15.4730",
        "yardStandalone": yard_standalone or {"active": False},
        "canEditNameSubjectPairs": can_edit_name_subject_pairs,
        "initialSubjectProfileId": initial_subject_profile_id,
        "urls": {
            "nameSubjectPairsModal": _name_subject_pairs_modal_url_template(),
            "activityFieldRules": reverse("waste_docs:activity_field_rules"),
            "followUpCandidates": reverse("waste_docs:follow_up_candidates"),
            "subjectOpenFollowUps": reverse("waste_docs:subject_open_follow_ups"),
            "suffixesByContext": reverse("waste_docs:suffixes_by_context"),
            "vehicleRzByActivity": reverse("waste_docs:vehicle_rz_by_activity"),
            "driversByContext": reverse("waste_docs:drivers_by_context"),
            "rideTemplatesByVehicleKind": reverse("waste_docs:ride_templates_by_vehicle_kind"),
            "subjectSearch": reverse("waste_docs:subject_search"),
            "subjectProfileByName": reverse("waste_docs:subject_profile_by_name"),
            "addressSuggestions": reverse("waste_docs:address_suggestions"),
            "addressGeocode": reverse("waste_docs:address_geocode"),
            "addressReverseGeocode": reverse("waste_docs:address_reverse_geocode"),
        },
    }
