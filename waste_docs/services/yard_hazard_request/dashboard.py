from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from users.services.access import can_see_all_waste_docs
from users.services.sberny_dvur import get_sberny_dvur_subject, is_sberny_dvur_role
from waste_docs.models import YardHazardousWasteRequest

# Horní mez OPEN hazardů na dashboardu (backlog jinak roste bez omezení).
DASHBOARD_HAZARD_OPEN_LIMIT = 100


def open_hazard_requests_for_dashboard(user: AbstractBaseUser, selected_date) -> list[YardHazardousWasteRequest]:
    qs = (
        YardHazardousWasteRequest.objects.filter(
            status=YardHazardousWasteRequest.Status.OPEN,
            submitted_date__lte=selected_date,
        )
        .select_related(
            "subject_profile",
            "subject_profile__name",
            "waste_type",
            "suffix",
            "vehicle_kind",
            "activity",
            "created_by",
        )
        .order_by("submitted_date", "created_at", "pk")
    )
    if can_see_all_waste_docs(user):
        return list(qs[:DASHBOARD_HAZARD_OPEN_LIMIT])
    if is_sberny_dvur_role(user):
        subj = get_sberny_dvur_subject(user)
        if subj:
            return list(qs.filter(subject_profile=subj)[:DASHBOARD_HAZARD_OPEN_LIMIT])
    return []
