"""Nabídka RZ pro založení průvodky ze sběrného dvora (nova-jizda)."""

from __future__ import annotations

from datetime import date

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair, VehicleRzProfile
from catalogs.services.name_subject_pair_vehicle_kinds import pair_vehicle_kind_ids
from waste_docs.models import SvozYardDriverPlan


def rz_options_for_yard_row(
    pair: NameSubjectWasteSuffixPair,
    subject: NameSubjectProfile,
    plan_date: date,
) -> list[dict]:
    """
    RZ pro řádek matice: profily vozidel podle druhu u páru + RZ z denního plánu dvora.
    """
    kind_ids = set(pair_vehicle_kind_ids(pair))
    by_pk: dict[int, dict] = {}

    if kind_ids:
        profiles = (
            VehicleRzProfile.objects.filter(vehicle_kinds__id__in=kind_ids)
            .select_related("rz")
            .distinct()
            .order_by("rz__value")
        )
        for profile in profiles:
            if profile.rz_id and profile.rz:
                by_pk[int(profile.rz_id)] = {
                    "pk": int(profile.rz_id),
                    "value": profile.rz.value,
                }

    plan_rows = (
        SvozYardDriverPlan.objects.filter(
            plan_date=plan_date,
            subject_profile=subject,
            vehicle_rz_id__isnull=False,
        )
        .select_related("vehicle_rz", "vehicle_kind")
        .order_by("sort_order", "vehicle_rz_id")
    )
    for row in plan_rows:
        vk_id = row.vehicle_kind_id
        if kind_ids and vk_id and vk_id not in kind_ids:
            continue
        if not row.vehicle_rz_id or not row.vehicle_rz:
            continue
        rz_pk = int(row.vehicle_rz_id)
        if rz_pk not in by_pk:
            by_pk[rz_pk] = {"pk": rz_pk, "value": row.vehicle_rz.value}

    return sorted(by_pk.values(), key=lambda item: (item.get("value") or "").lower())
