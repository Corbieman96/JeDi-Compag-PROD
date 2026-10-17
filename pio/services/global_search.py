from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from django.db.models import Q
from django.utils import timezone

from catalogs.models import NameSubjectWasteSuffixPair
from pio.models import PioRevision

_PAIR_SELECT = (
    "pair",
    "pair__subject_profile",
    "pair__subject_profile__name",
    "pair__waste_type",
    "pair__suffix",
)

_ACTIVE_PAIR_SELECT = (
    "subject_profile",
    "subject_profile__name",
    "waste_type",
    "suffix",
)


def _text_filter_q(q: str) -> Q:
    return (
        Q(subject_profile__company_name__icontains=q)
        | Q(subject_profile__name__value__icontains=q)
        | Q(waste_type__value__icontains=q)
        | Q(waste_type__code__icontains=q)
        | Q(suffix__value__icontains=q)
    )


def _revision_text_filter_q(q: str) -> Q:
    return (
        Q(pair__subject_profile__company_name__icontains=q)
        | Q(pair__subject_profile__name__value__icontains=q)
        | Q(pair__waste_type__value__icontains=q)
        | Q(pair__waste_type__code__icontains=q)
        | Q(pair__suffix__value__icontains=q)
        | Q(note__icontains=q)
    )


@dataclass(frozen=True)
class PioSearchItem:
    kind: Literal["active", "revision"]
    sort_at: datetime
    pair: NameSubjectWasteSuffixPair
    note: str
    file: object
    revision: PioRevision | None = None
    sort_key: int = 0

    @property
    def kind_label(self) -> str:
        return "Aktivní" if self.kind == "active" else "Archiv"


def _revision_items(
    *,
    q: str,
    date_from: date | None,
    date_to: date | None,
    fetch_limit: int,
) -> list[PioSearchItem]:
    qs = PioRevision.objects.select_related(*_PAIR_SELECT, "created_by")
    if q:
        qs = qs.filter(_revision_text_filter_q(q))
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    items: list[PioSearchItem] = []
    for rev in qs.order_by("-created_at", "-pk")[:fetch_limit]:
        items.append(
            PioSearchItem(
                kind="revision",
                sort_at=rev.created_at,
                pair=rev.pair,
                note=rev.note,
                file=rev.file,
                revision=rev,
                sort_key=rev.pk,
            )
        )
    return items


def _active_items(
    *,
    q: str,
    date_from: date | None,
    date_to: date | None,
    fetch_limit: int,
) -> list[PioSearchItem]:
    qs = (
        NameSubjectWasteSuffixPair.objects.exclude(pio_document="")
        .exclude(pio_document__isnull=True)
        .select_related(*_ACTIVE_PAIR_SELECT)
    )
    if q:
        qs = qs.filter(_text_filter_q(q))
    if date_from:
        qs = qs.filter(subject_profile__updated_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(subject_profile__updated_at__date__lte=date_to)

    items: list[PioSearchItem] = []
    for pair in qs.order_by("-subject_profile__updated_at", "-pk")[:fetch_limit]:
        updated = pair.subject_profile.updated_at
        if timezone.is_naive(updated):
            updated = timezone.make_aware(updated)
        items.append(
            PioSearchItem(
                kind="active",
                sort_at=updated,
                pair=pair,
                note="",
                file=pair.pio_document,
                revision=None,
                sort_key=pair.pk,
            )
        )
    return items


def search_pio_items(
    *,
    q: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 500,
) -> list[PioSearchItem]:
    fetch_limit = limit
    revision_items = _revision_items(q=q, date_from=date_from, date_to=date_to, fetch_limit=fetch_limit)
    active_items = _active_items(q=q, date_from=date_from, date_to=date_to, fetch_limit=fetch_limit)
    merged = revision_items + active_items
    merged.sort(key=lambda item: (item.sort_at, item.sort_key), reverse=True)
    return merged[:limit]
