"""Úzké výběry řádků SuffixCatalog pro formuláře (bez zdvojených „stejných“ koncovek)."""

from __future__ import annotations

import unicodedata
from typing import Iterable

from django.apps import apps
from django.db.models import QuerySet

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair, SuffixCatalog, SuffixSiteProfile


def _norm_suffix_label(value: str) -> str:
    return unicodedata.normalize("NFC", (value or "").strip().casefold())


def referenced_suffix_catalog_ids() -> set[int]:
    """PK řádků SuffixCatalog, na které někde v systému ukazuje FK (nebo M2M)."""
    ids: set[int] = set()
    ids.update(NameSubjectWasteSuffixPair.objects.values_list("suffix_id", flat=True))
    Through = NameSubjectProfile.allowed_suffixes.through
    ids.update(Through.objects.values_list("suffixcatalog_id", flat=True))
    ids.update(SuffixSiteProfile.objects.values_list("suffix_id", flat=True))
    Pruvodka = apps.get_model("waste_docs", "Pruvodka")
    ids.update(Pruvodka.objects.exclude(suffix_id=None).values_list("suffix_id", flat=True))
    ids.discard(None)
    return ids


def suffix_catalog_queryset_for_subject_pair_select(*, must_include_ids: Iterable[int]) -> QuerySet[SuffixCatalog]:
    """
    Kompletní číselník koncovek (model ``SuffixCatalog``), stejný zdroj jako evidence u
    ``/catalogs/suffix/`` (profil zařízení je vázaný na řádek ``SuffixCatalog``).

    U řádků se stejným normalizovaným textem (mezery, Unicode) zůstane ve výběru jedna volba —
    preferuje se řádek, který je někde v systému referencovaný, jinak řádek s nižším PK.
    Aktuální výběr na řádku formuláře (``must_include_ids``) je vždy zahrnutý.
    """
    must = {int(pk) for pk in must_include_ids if pk}
    referenced = referenced_suffix_catalog_ids()
    rows = list(SuffixCatalog.objects.all())
    rows.sort(key=lambda r: (_norm_suffix_label(r.value), 0 if r.pk in referenced else 1, r.pk))
    seen: set[str] = set()
    chosen: list[int] = []
    for r in rows:
        key = _norm_suffix_label(r.value)
        if key in seen:
            continue
        seen.add(key)
        chosen.append(r.pk)
    chosen_set = set(chosen) | must
    by_pk = {r.pk: r for r in rows}
    must_by_norm: dict[str, list[int]] = {}
    for pk in must:
        o = by_pk.get(pk)
        if o:
            must_by_norm.setdefault(_norm_suffix_label(o.value), []).append(pk)
    thin_must = set()
    for pks in must_by_norm.values():
        thin_must.add(min(pks))
    chosen_set = (chosen_set - must) | thin_must
    return SuffixCatalog.objects.filter(pk__in=chosen_set).order_by("value")
