"""Jedno načtení sběrných dvorů + denního plánu pro dashboard (request-scoped)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date

from catalogs.models import NameSubjectProfile
from waste_docs.models import SvozYardDriverPlan

_bundle_var: ContextVar["CollectionYardDayBundle | None"] = ContextVar(
    "collection_yard_day_bundle",
    default=None,
)


@dataclass(frozen=True)
class CollectionYardDayBundle:
    plan_date: date
    yards: tuple[NameSubjectProfile, ...]
    yard_ids: frozenset[int]
    plan_rows: tuple[SvozYardDriverPlan, ...]


def get_collection_yard_day_bundle(plan_date: date) -> CollectionYardDayBundle:
    """Yards + SvozYardDriverPlan pro den — v rámci requestu max. jedna DB sada."""
    existing = _bundle_var.get()
    if existing is not None and existing.plan_date == plan_date:
        return existing

    yards = tuple(
        NameSubjectProfile.objects.filter(yard_settings__is_collection_yard=True)
        .order_by("company_name", "pk")
        .only("pk", "company_name")
    )
    yard_ids = frozenset(y.pk for y in yards)
    plan_rows: tuple[SvozYardDriverPlan, ...] = ()
    if yard_ids:
        plan_rows = tuple(
            SvozYardDriverPlan.objects.filter(
                plan_date=plan_date,
                subject_profile_id__in=yard_ids,
            )
            .select_related("driver", "vehicle_rz", "vehicle_kind")
            .order_by(
                "subject_profile_id",
                "row_kind",
                "vehicle_kind_id",
                "sort_order",
                "driver_id",
                "pk",
            )
        )
    bundle = CollectionYardDayBundle(
        plan_date=plan_date,
        yards=yards,
        yard_ids=yard_ids,
        plan_rows=plan_rows,
    )
    _bundle_var.set(bundle)
    return bundle
