"""Načtení denního plánu svozů jednou do paměti — stejné párování jako resolve_svoz_plan_rows."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field

from catalogs.models.vehicle_rz import VehicleRzProfile
from waste_docs.models import SvozYardDriverPlan
from waste_docs.services.svoz_dispatch.plan_lookup_scope import subject_profile_ids_for_plan_lookup
from waste_docs.services.svoz_dispatch.plan_row_resolution import (
    ORDER_BY_PLAN_ROWS,
    _prefer_own_yard_plan_rows,
    match_equivalent_vehicle_kind_aliases,
    match_exact_plan_vehicle_kind,
    match_plan_rows_with_unspecified_vehicle_kind,
    match_yard_linked_vehicle_kinds,
)

_resolve_cache_var: ContextVar["DayPlanResolveCache | None"] = ContextVar(
    "day_plan_resolve_cache",
    default=None,
)


def _row_kind_value(row_kind) -> str:
    if isinstance(row_kind, str):
        return row_kind
    return getattr(row_kind, "value", str(row_kind))



class PlanRowsView:
    """Duck-typed subset QuerySet: filter / order_by / list() nad už načtenými řádky."""

    def __init__(self, rows: list[SvozYardDriverPlan]):
        self._rows = list(rows)

    def filter(self, **kwargs):
        rows = self._rows
        if "vehicle_kind_id" in kwargs:
            vid = kwargs["vehicle_kind_id"]
            rows = [r for r in rows if r.vehicle_kind_id == vid]
        if "vehicle_kind_id__in" in kwargs:
            ids = set(kwargs["vehicle_kind_id__in"])
            rows = [r for r in rows if r.vehicle_kind_id in ids]
        if "vehicle_kind__isnull" in kwargs:
            want_null = bool(kwargs["vehicle_kind__isnull"])
            rows = [r for r in rows if (r.vehicle_kind_id is None) is want_null]
        if "vehicle_rz_id__isnull" in kwargs:
            want_null = bool(kwargs["vehicle_rz_id__isnull"])
            rows = [r for r in rows if (r.vehicle_rz_id is None) is want_null]
        return PlanRowsView(rows)

    def order_by(self, *fields: str):
        def sort_key(r: SvozYardDriverPlan):
            parts = []
            for f in fields:
                val = getattr(r, f, None)
                parts.append(0 if val is None else val)
            return tuple(parts)

        return PlanRowsView(sorted(self._rows, key=sort_key))

    def __iter__(self):
        return iter(self._rows)

    def __bool__(self):
        return bool(self._rows)

    def __len__(self):
        return len(self._rows)


@dataclass
class DayPlanResolveCache:
    plan_date: object
    rows: list[SvozYardDriverPlan] = field(default_factory=list)
    profiles_by_rz: dict[int, VehicleRzProfile] = field(default_factory=dict)
    _scope_cache: dict[int, list[int]] = field(default_factory=dict)

    @classmethod
    def load(cls, plan_date) -> DayPlanResolveCache:
        existing = _resolve_cache_var.get()
        if existing is not None and existing.plan_date == plan_date:
            return existing
        rows = list(
            SvozYardDriverPlan.objects.filter(plan_date=plan_date).order_by(
                "sort_order", "driver_id", "pk"
            )
        )
        rz_ids = {r.vehicle_rz_id for r in rows if r.vehicle_rz_id}
        profiles: dict[int, VehicleRzProfile] = {}
        if rz_ids:
            profiles = {
                p.rz_id: p
                for p in VehicleRzProfile.objects.filter(rz_id__in=rz_ids).prefetch_related(
                    "vehicle_kinds"
                )
            }
        cache = cls(plan_date=plan_date, rows=rows, profiles_by_rz=profiles)
        _resolve_cache_var.set(cache)
        return cache

    def scope_ids(self, subject_profile_id: int) -> list[int]:
        sid = int(subject_profile_id)
        cached = self._scope_cache.get(sid)
        if cached is None:
            cached = subject_profile_ids_for_plan_lookup(sid)
            self._scope_cache[sid] = cached
        return cached

    def base_view(self, subject_profile_id: int, row_kind) -> PlanRowsView:
        scope = set(self.scope_ids(subject_profile_id))
        rk = _row_kind_value(row_kind)
        filtered = [
            r
            for r in self.rows
            if r.subject_profile_id in scope and _row_kind_value(r.row_kind) == rk
        ]
        return PlanRowsView(filtered)

    def resolve(
        self,
        *,
        subject_profile_id: int,
        yard_vehicle_kind_id: int | None,
        row_kind,
    ) -> list[SvozYardDriverPlan]:
        base = self.base_view(subject_profile_id, row_kind)
        steps = (
            match_exact_plan_vehicle_kind,
            match_equivalent_vehicle_kind_aliases,
            match_yard_linked_vehicle_kinds,
            match_plan_rows_with_unspecified_vehicle_kind,
            self._match_via_rz,
        )
        for step in steps:
            found = step(base, yard_vehicle_kind_id, subject_profile_id)
            if found:
                return _prefer_own_yard_plan_rows(found, primary_subject_id=subject_profile_id)
        return []

    def _match_via_rz(
        self,
        base: PlanRowsView,
        yard_vehicle_kind_id: int | None,
        subject_profile_id: int,
    ) -> list[SvozYardDriverPlan]:
        # Stejná logika jako match_plan_rows_via_rz_profile_vehicle_kinds, ale bez DB.
        if yard_vehicle_kind_id is None:
            return []
        # Dočasně naplnit stejný tvar přes existující funkci: podstrčit prázdný queryset
        # nejde — proto inline kopie s profiles_by_rz.
        from waste_docs.services.svoz_dispatch.plan_row_resolution import (
            _compatible_kind_ids_for_plan_matching,
        )

        vk_mid = int(yard_vehicle_kind_id)
        rows = list(base.filter(vehicle_rz_id__isnull=False).order_by(*ORDER_BY_PLAN_ROWS))
        if not rows:
            return []
        equiv = _compatible_kind_ids_for_plan_matching(subject_profile_id, vk_mid) or {vk_mid}
        rz_ok: set[int] = set()
        for rz_id in {r.vehicle_rz_id for r in rows if r.vehicle_rz_id}:
            prof = self.profiles_by_rz.get(rz_id)
            if not prof:
                continue
            vk_pks = {k.pk for k in prof.vehicle_kinds.all()}
            if equiv.intersection(vk_pks):
                rz_ok.add(rz_id)
        return [r for r in rows if r.vehicle_rz_id and r.vehicle_rz_id in rz_ok]


def plan_has_driver_pool_cached(
    cache: DayPlanResolveCache,
    *,
    subject_profile_id: int,
    vehicle_kind_id: int,
    row_kind: str,
) -> bool:
    rows = cache.resolve(
        subject_profile_id=subject_profile_id,
        yard_vehicle_kind_id=vehicle_kind_id,
        row_kind=row_kind,
    )
    return any(r.driver_id and r.vehicle_rz_id for r in rows)


def plan_has_driver_for_exception_slot_cached(
    cache: DayPlanResolveCache,
    *,
    subject_profile_id: int,
    vehicle_kind_id: int,
    sort_order: int,
) -> bool:
    rows = cache.resolve(
        subject_profile_id=subject_profile_id,
        yard_vehicle_kind_id=vehicle_kind_id,
        row_kind=SvozYardDriverPlan.RowKind.EXCEPTION,
    )
    for row in rows:
        if row.sort_order == sort_order and row.driver_id and row.vehicle_rz_id:
            return True
    return False


__all__ = [
    "DayPlanResolveCache",
    "PlanRowsView",
    "plan_has_driver_for_exception_slot_cached",
    "plan_has_driver_pool_cached",
]
