"""Vyhledávání subjektu F/P pro pole „Subjekt sběrného dvora“ ve formuláři uživatele."""

from __future__ import annotations

from django.db.models import Q

from catalogs.models import NameSubjectProfile
from waste_docs.services.search_normalize import normalize_search_text

_MIN_QUERY_LEN = 2
_DEFAULT_LIMIT = 25


def sberny_dvur_subject_label(profile: NameSubjectProfile) -> str:
    ico = profile.ico.value if profile.ico_id else "bez IČO"
    name_val = (profile.name.value if profile.name_id else "").strip()
    base = f"{profile.company_name} ({ico})"
    if name_val:
        base = f"{base} · {name_val}"
    if _profile_is_collection_yard(profile):
        return f"[SBĚR] {base}"
    return base


def sberny_dvur_subject_title(profile: NameSubjectProfile) -> str:
    parts = [profile.company_name or ""]
    if profile.ico_id:
        parts.append(f"IČO {profile.ico.value}")
    if profile.name_id:
        parts.append(f"F/P {profile.name.value}")
    parts.append(f"ID subjektu {profile.pk}")
    if _profile_is_collection_yard(profile):
        parts.append("Lokalita sběrného dvora")
    return " · ".join(p for p in parts if p)


def _profile_is_collection_yard(profile: NameSubjectProfile) -> bool:
    yard = getattr(profile, "yard_settings", None)
    return bool(yard and yard.is_collection_yard)


def _base_queryset():
    return NameSubjectProfile.objects.select_related("name", "ico", "yard_settings")


def _rows_to_payload(items: list[NameSubjectProfile]) -> list[dict]:
    rows = []
    for profile in items:
        rows.append(
            {
                "subject_profile_id": profile.pk,
                "label": sberny_dvur_subject_label(profile),
                "title": sberny_dvur_subject_title(profile),
                "is_collection_yard": _profile_is_collection_yard(profile),
            }
        )
    return rows


def search_sberny_dvur_subjects(query: str, *, limit: int = _DEFAULT_LIMIT) -> list[dict]:
    q = (query or "").strip()
    if len(q) < _MIN_QUERY_LEN:
        return []

    qs = (
        _base_queryset()
        .filter(
            Q(ico__value__icontains=q)
            | Q(name__value__icontains=q)
            | Q(company_name__icontains=q)
        )
        .order_by("-yard_settings__is_collection_yard", "company_name", "pk")
    )
    items = list(qs[:limit])
    if not items:
        q_norm = normalize_search_text(q)
        matched = []
        for row in _base_queryset().order_by("-yard_settings__is_collection_yard", "company_name", "pk")[:1200]:
            blob = normalize_search_text(
                " ".join(
                    [
                        row.ico.value if row.ico_id else "",
                        row.name.value if row.name_id else "",
                        row.company_name or "",
                    ]
                )
            )
            if q_norm in blob:
                matched.append(row)
            if len(matched) >= limit:
                break
        items = matched
    return _rows_to_payload(items)
