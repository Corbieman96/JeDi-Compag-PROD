"""Subjekt F/P: páry odpad–koncovka a odvozené M2M."""

from catalogs.models import NameSubjectProfile


def sync_subject_allowed_from_pairs(profile: NameSubjectProfile) -> None:
    """Z `waste_suffix_pairs` doplní `allowed_waste_types` a `allowed_suffixes`."""
    qs = profile.waste_suffix_pairs.all()
    profile.allowed_waste_types.set(qs.values_list("waste_type_id", flat=True).distinct())
    profile.allowed_suffixes.set(qs.values_list("suffix_id", flat=True).distinct())
