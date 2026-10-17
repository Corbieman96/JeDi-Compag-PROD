"""Vyhledání řádků denního plánu dvora podle data, dvoru, kind řádku a druhu z matice."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from django.db.models import QuerySet

from catalogs.models import NameSubjectWasteSuffixPair
from catalogs.models.vehicle_rz import VehicleRzProfile
from waste_docs.models import SvozYardDriverPlan
from waste_docs.services.svoz_dispatch.exception_slot import exception_slot_for_pair

from waste_docs.services.svoz_dispatch.plan_coverage import _row_kind_value
from waste_docs.services.svoz_dispatch.plan_lookup_scope import subject_profile_ids_for_plan_lookup
from catalogs.services.vehicle_kind_compatibility import vehicle_kinds_covering_task
from waste_docs.services.svoz_dispatch.vehicle_kind_equivalence import (
    equivalent_vehicle_kind_ids_for_plan_matching,
    equivalent_vehicle_kind_ids_for_yard,
)


def _compatible_kind_ids_for_plan_matching(
    subject_profile_id: int,
    yard_vehicle_kind_id: int,
) -> set[int]:
    """Ekvivalence názvu/zkratky + směrově pokrývající druhy ze stromu parent_kind."""
    out = set(equivalent_vehicle_kind_ids_for_yard(subject_profile_id, int(yard_vehicle_kind_id)))
    out |= set(vehicle_kinds_covering_task(int(yard_vehicle_kind_id)))
    return out

ORDER_BY_PLAN_ROWS = ("sort_order", "driver_id")

MatchStepFn = Callable[
    [QuerySet[SvozYardDriverPlan], int | None, int],
    list[SvozYardDriverPlan],
]


def _base_plan_qs(plan_date, subject_profile_ids: Sequence[int], row_kind) -> QuerySet[SvozYardDriverPlan]:
    rk = _row_kind_value(row_kind)
    ids = list(dict.fromkeys(int(x) for x in subject_profile_ids))
    return SvozYardDriverPlan.objects.filter(
        plan_date=plan_date,
        subject_profile_id__in=ids,
        row_kind=rk,
    )


def _sort_plan_rows_for_primary(plan_rows: list[SvozYardDriverPlan], *, primary_subject_id: int) -> list[SvozYardDriverPlan]:
    return sorted(
        plan_rows,
        key=lambda r: (
            0 if r.subject_profile_id == primary_subject_id else 1,
            r.sort_order,
            r.driver_id,
            r.pk,
        ),
    )


def _prefer_own_yard_plan_rows(
    plan_rows: list[SvozYardDriverPlan],
    *,
    primary_subject_id: int,
) -> list[SvozYardDriverPlan]:
    """Vlastní SD má prioritu; řidiči partnera ve skupině jen když vlastní plán chybí."""
    own = [r for r in plan_rows if r.subject_profile_id == primary_subject_id]
    pool = own if own else plan_rows
    return _sort_plan_rows_for_primary(pool, primary_subject_id=primary_subject_id)


def match_exact_plan_vehicle_kind(
    base: QuerySet[SvozYardDriverPlan],
    yard_vehicle_kind_id: int | None,
    _subject_profile_id: int,
) -> list[SvozYardDriverPlan]:
    if yard_vehicle_kind_id is None:
        return []
    return list(base.filter(vehicle_kind_id=yard_vehicle_kind_id).order_by(*ORDER_BY_PLAN_ROWS))


def match_equivalent_vehicle_kind_aliases(
    base: QuerySet[SvozYardDriverPlan],
    yard_vehicle_kind_id: int | None,
    _subject_profile_id: int,
) -> list[SvozYardDriverPlan]:
    if yard_vehicle_kind_id is None:
        return []
    equiv = list(equivalent_vehicle_kind_ids_for_plan_matching(int(yard_vehicle_kind_id)))
    if not equiv:
        return []
    return list(base.filter(vehicle_kind_id__in=equiv).order_by(*ORDER_BY_PLAN_ROWS))


def match_yard_linked_vehicle_kinds(
    base: QuerySet[SvozYardDriverPlan],
    yard_vehicle_kind_id: int | None,
    subject_profile_id: int,
) -> list[SvozYardDriverPlan]:
    """Druhy z matice téhož dvora ve stejné ekvivalence třídě jako druh na řádku požadavku."""
    if yard_vehicle_kind_id is None:
        return []
    equiv = list(_compatible_kind_ids_for_plan_matching(subject_profile_id, int(yard_vehicle_kind_id)))
    if not equiv:
        return []
    return list(base.filter(vehicle_kind_id__in=equiv).order_by(*ORDER_BY_PLAN_ROWS))


def match_plan_rows_with_unspecified_vehicle_kind(
    base: QuerySet[SvozYardDriverPlan],
    _yard_vehicle_kind_id: int | None,
    _subject_profile_id: int,
) -> list[SvozYardDriverPlan]:
    return list(base.filter(vehicle_kind__isnull=True).order_by(*ORDER_BY_PLAN_ROWS))


def match_plan_rows_via_rz_profile_vehicle_kinds(
    base: QuerySet[SvozYardDriverPlan],
    yard_vehicle_kind_id: int | None,
    subject_profile_id: int,
) -> list[SvozYardDriverPlan]:
    if yard_vehicle_kind_id is None:
        return []
    vk_mid = int(yard_vehicle_kind_id)
    rows = list(base.filter(vehicle_rz_id__isnull=False).order_by(*ORDER_BY_PLAN_ROWS))
    if not rows:
        return []
    rz_ids = {r.vehicle_rz_id for r in rows if r.vehicle_rz_id}
    if not rz_ids:
        return []

    profiles = {
        p.rz_id: p
        for p in VehicleRzProfile.objects.filter(rz_id__in=rz_ids).prefetch_related("vehicle_kinds")
    }

    equiv = _compatible_kind_ids_for_plan_matching(subject_profile_id, vk_mid) or {vk_mid}

    rz_with_matrix_kind: set[int] = set()
    for rz_id, prof in profiles.items():
        vk_pks = {k.pk for k in prof.vehicle_kinds.all()}
        if equiv.intersection(vk_pks):
            rz_with_matrix_kind.add(rz_id)

    return [r for r in rows if r.vehicle_rz_id and r.vehicle_rz_id in rz_with_matrix_kind]


PLAN_ROW_MATCH_STEPS: Sequence[MatchStepFn] = (
    match_exact_plan_vehicle_kind,
    match_equivalent_vehicle_kind_aliases,
    match_yard_linked_vehicle_kinds,
    match_plan_rows_with_unspecified_vehicle_kind,
    match_plan_rows_via_rz_profile_vehicle_kinds,
)


def resolve_svoz_plan_rows(
    *,
    plan_date,
    subject_profile_id: int,
    yard_vehicle_kind_id: int | None,
    row_kind,
) -> list[SvozYardDriverPlan]:
    scope_ids = subject_profile_ids_for_plan_lookup(subject_profile_id)
    base = _base_plan_qs(plan_date, scope_ids, row_kind)
    for step in PLAN_ROW_MATCH_STEPS:
        found = step(base, yard_vehicle_kind_id, subject_profile_id)
        if found:
            return _prefer_own_yard_plan_rows(found, primary_subject_id=subject_profile_id)
    return []


def resolve_svoz_plan_rows_for_assignment(
    *,
    plan_date,
    subject_profile_id: int,
    yard_vehicle_kind_id: int | None,
    yard_svoz_auto_assign_driver: bool,
    pair=None,
) -> list[SvozYardDriverPlan]:
    """
    Řádky plánu pro přiřazení úkolu / matici.

    Nejprve skupina podle příznaku řádku matice (běžný vs. výjimka).
    U výjimky se slotem V1–V4 v číselníku se **nepoužije** fallback na běžný svoz B1–B4 —
    bez vyplněného V-slotu zůstane úkol otevřený na dashboardu.
    """
    primary = (
        SvozYardDriverPlan.RowKind.STANDARD
        if yard_svoz_auto_assign_driver
        else SvozYardDriverPlan.RowKind.EXCEPTION
    )
    secondary = (
        SvozYardDriverPlan.RowKind.EXCEPTION
        if yard_svoz_auto_assign_driver
        else SvozYardDriverPlan.RowKind.STANDARD
    )
    rows = resolve_svoz_plan_rows(
        plan_date=plan_date,
        subject_profile_id=subject_profile_id,
        yard_vehicle_kind_id=yard_vehicle_kind_id,
        row_kind=primary,
    )
    if rows:
        return rows
    if (
        pair is not None
        and isinstance(pair, NameSubjectWasteSuffixPair)
        and not yard_svoz_auto_assign_driver
        and exception_slot_for_pair(pair) is not None
    ):
        return []
    return resolve_svoz_plan_rows(
        plan_date=plan_date,
        subject_profile_id=subject_profile_id,
        yard_vehicle_kind_id=yard_vehicle_kind_id,
        row_kind=secondary,
    )
