"""Odeslání nebezpečného odpadu ze sběrného dvora — deduplikace otevřených požadavků."""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser

from catalogs.models import NameSubjectProfile
from waste_docs.models import YardHazardousWasteRequest
from waste_docs.services.svoz_matrix_post_collect import SvozPendingLine
from waste_docs.services.yard_hazard_request.create import create_hazard_request_from_line


@dataclass(frozen=True)
class HazardSubmitResult:
    created: bool
    skipped_duplicate: bool
    existing: YardHazardousWasteRequest | None = None


def find_open_hazard_for_pair(
    *,
    subject_profile_id: int,
    pair_id: int,
) -> YardHazardousWasteRequest | None:
    return (
        YardHazardousWasteRequest.objects.filter(
            subject_profile_id=subject_profile_id,
            source_waste_suffix_pair_id=pair_id,
            status=YardHazardousWasteRequest.Status.OPEN,
        )
        .order_by("submitted_date", "created_at", "pk")
        .first()
    )


def submit_hazard_line_if_allowed(
    pline: SvozPendingLine,
    subject: NameSubjectProfile,
    user: AbstractBaseUser,
) -> HazardSubmitResult:
    """
    Vytvoří požadavek na nebezpečný odpad, pokud pro stejný pár odpad–koncovka
    ještě neexistuje otevřený záznam. Duplicitu tiše přeskočí (bez přepsání dat).
    """
    existing = find_open_hazard_for_pair(
        subject_profile_id=subject.pk,
        pair_id=pline.pair.pk,
    )
    if existing is not None:
        return HazardSubmitResult(created=False, skipped_duplicate=True, existing=existing)
    created = create_hazard_request_from_line(pline, subject, user)
    return HazardSubmitResult(created=True, skipped_duplicate=False, existing=created)
