from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from catalogs.models import NameSubjectProfile
from catalogs.services.name_subject_pair_vehicle_kinds import (
    pair_vehicle_kind_ids,
    sync_pair_primary_vehicle_kind_fk,
)
from waste_docs.models import YardHazardousWasteRequest
from waste_docs.services.svoz_matrix_post_collect import SvozPendingLine


def create_hazard_request_from_line(
    pline: SvozPendingLine,
    subject: NameSubjectProfile,
    user: AbstractBaseUser,
) -> YardHazardousWasteRequest:
    pair = pline.pair
    sync_pair_primary_vehicle_kind_fk(pair)
    kind_ids = pair_vehicle_kind_ids(pair)
    vehicle_kind_id = kind_ids[0] if kind_ids else pair.yard_vehicle_kind_id

    return YardHazardousWasteRequest.objects.create(
        subject_profile=subject,
        created_by=user,
        waste_type_id=pair.waste_type_id,
        suffix_id=pair.suffix_id,
        source_waste_suffix_pair=pair,
        vehicle_kind_id=vehicle_kind_id,
        activity_id=pair.yard_svoz_activity_id,
        container_numbers=pline.container_numbers,
        matrix_display_label=pline.matrix_display_label,
        yard_contact_note=pline.yard_contact_note,
        submitted_date=timezone.localdate(),
    )
