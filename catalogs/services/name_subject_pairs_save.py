"""Sdílené ukládání formsetu Povolené odpady a koncovky u subjektu F/P."""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import AbstractBaseUser
from django.http import QueryDict

from catalogs.forms.name_subject_pairs import NameSubjectWasteSuffixPairFormSet
from catalogs.models import NameSubjectProfile
from catalogs.services.subject_disposal import sync_subject_allowed_from_pairs
from catalogs.services.waste_pair_sort import normalize_waste_suffix_pair_sort_order
from users.services.access import can_see_all_waste_docs


@dataclass
class PairsSaveResult:
    ok: bool
    formset: NameSubjectWasteSuffixPairFormSet | None = None
    error_text: str = ""


def apply_pairs_ordering(formset: NameSubjectWasteSuffixPairFormSet) -> None:
    formset.queryset = formset.queryset.order_by("sort_order", "id")


def build_pair_formset(
    user: AbstractBaseUser,
    instance: NameSubjectProfile,
    *,
    data: QueryDict | None = None,
    files=None,
) -> NameSubjectWasteSuffixPairFormSet:
    kwargs: dict = {
        "instance": instance,
        "form_kwargs": {
            "show_dispatch_plan_fields": can_see_all_waste_docs(user),
            "actor_user": user,
            "subject_profile": instance,
        },
    }
    if data is not None:
        kwargs["data"] = data
    if files is not None:
        kwargs["files"] = files
    return NameSubjectWasteSuffixPairFormSet(**kwargs)


def format_pair_formset_errors(formset: NameSubjectWasteSuffixPairFormSet) -> str:
    parts: list[str] = []
    if formset.non_form_errors():
        parts.extend(str(e) for e in formset.non_form_errors())
    for idx, f in enumerate(formset.forms, start=1):
        if not f.errors:
            continue
        for field_name, errors in f.errors.items():
            if field_name == "__all__":
                for err in errors:
                    parts.append(f"Pár #{idx}: {err}")
                continue
            field = f.fields.get(field_name)
            label = field.label if field else field_name
            for err in errors:
                parts.append(f"Pár #{idx} / {label}: {err}")
    return " | ".join(parts)


def save_name_subject_waste_suffix_pairs(
    profile: NameSubjectProfile,
    user: AbstractBaseUser,
    post: QueryDict,
    files,
) -> PairsSaveResult:
    had_pairs = profile.waste_suffix_pairs.exists()
    formset = build_pair_formset(user, profile, data=post, files=files)
    if not formset.is_valid():
        return PairsSaveResult(ok=False, formset=formset, error_text=format_pair_formset_errors(formset))
    formset.save()
    normalize_waste_suffix_pair_sort_order(formset)
    if profile.waste_suffix_pairs.exists():
        sync_subject_allowed_from_pairs(profile)
    elif had_pairs:
        profile.allowed_waste_types.clear()
        profile.allowed_suffixes.clear()
    return PairsSaveResult(ok=True, formset=formset)
