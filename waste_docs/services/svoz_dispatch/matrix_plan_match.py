"""Párování řádku matice sběrného dvora s plánem svozů (bez blokace odeslání formuláře)."""

from __future__ import annotations

from datetime import date

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair
from catalogs.models.vehicle_rz import VehicleRzProfile
from catalogs.services.name_subject_pair_vehicle_kinds import pair_vehicle_kind_ids

from waste_docs.services.svoz_dispatch.assignment import planned_assignment_for_matrix_row
from catalogs.services.vehicle_kind_compatibility import rz_profile_serves_task_kind


def planned_driver_and_rz_for_matrix_pair(
    subject: NameSubjectProfile,
    pair: NameSubjectWasteSuffixPair,
    target_date: date,
) -> tuple[int | None, int | None, int | None]:
    """(driver_id, vehicle_rz_id, matched_vehicle_kind_id) z plánu, nebo (None, None, None)."""
    for vk_id in pair_vehicle_kind_ids(pair):
        driver_id, rz_id = planned_assignment_for_matrix_row(
            subject_profile_id=subject.pk,
            target_date=target_date,
            vehicle_kind_id=vk_id,
            yard_svoz_auto_assign_driver=pair.yard_svoz_auto_assign_driver,
            pair=pair,
        )
        if driver_id and rz_id:
            return driver_id, rz_id, vk_id
    return None, None, None


def auto_pruvodka_blocked_by_rz_profile(
    pair: NameSubjectWasteSuffixPair,
    rz_id: int | None,
    *,
    subject_profile_id: int,
    task_vehicle_kind_id: int | None = None,
) -> bool:
    """
    True, pokud je RZ z plánu, ale profil RZ v číselníku nepokrývá druh vozidla z matice
    (auto-založení průvodky by stejně selhalo).
    """
    kind_ids = pair_vehicle_kind_ids(pair)
    if not rz_id or not kind_ids:
        return False
    prof = VehicleRzProfile.objects.filter(rz_id=rz_id).prefetch_related("vehicle_kinds").first()
    if not prof:
        return True
    if task_vehicle_kind_id is not None:
        return not rz_profile_serves_task_kind(prof, int(task_vehicle_kind_id))
    return not any(rz_profile_serves_task_kind(prof, vk_id) for vk_id in kind_ids)


def matrix_pair_resolves_to_plan_assignment(
    subject: NameSubjectProfile,
    pair: NameSubjectWasteSuffixPair,
    target_date: date,
) -> bool:
    """Zda lze z plánu přiřadit řidiče i RZ a auto-založit průvodku."""
    driver_id, rz_id, vk_id = planned_driver_and_rz_for_matrix_pair(subject, pair, target_date)
    if not driver_id or not rz_id:
        return False
    if auto_pruvodka_blocked_by_rz_profile(
        pair, rz_id, subject_profile_id=subject.pk, task_vehicle_kind_id=vk_id
    ):
        return False
    return True
