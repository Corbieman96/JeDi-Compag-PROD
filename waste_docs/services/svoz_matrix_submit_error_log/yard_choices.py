"""Seznam sběrných dvorů pro výběr na stránce Log SD."""

from __future__ import annotations

from catalogs.models import NameSubjectProfile


def yard_display_label(subject: NameSubjectProfile) -> str:
    label = (getattr(subject, "company_name", None) or "").strip()
    if not label and getattr(subject, "name", None) is not None:
        label = (getattr(subject.name, "value", None) or "").strip()
    if not label:
        label = f"Dvůr #{subject.pk}"
    return label


def collection_yard_choices() -> list[dict]:
    qs = (
        NameSubjectProfile.objects.filter(yard_settings__is_collection_yard=True)
        .select_related("name")
        .order_by("company_name", "pk")
    )
    return [{"id": row.pk, "label": yard_display_label(row)} for row in qs]


def collection_yard_or_none(*, subject_id: int | None) -> NameSubjectProfile | None:
    if not subject_id:
        return None
    return (
        NameSubjectProfile.objects.filter(
            pk=subject_id,
            yard_settings__is_collection_yard=True,
        )
        .select_related("name")
        .first()
    )
