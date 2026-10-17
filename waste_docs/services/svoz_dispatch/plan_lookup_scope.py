"""Rozsah subjektů F/P, u kterých se hledá uložený plán svozů pro matici daného dvora."""

from __future__ import annotations

from catalogs.models import NameSubjectProfile


def subject_profile_ids_for_plan_lookup(subject_profile_id: int) -> list[int]:
    """
    ID subjektů, jejichž řádky ``SvozYardDriverPlan`` platí pro matici tohoto dvora.

    Pořadí: vlastní subjekt → ostatní sběrné dvory se stejnou ``yard_svoz_dispatch_group``.
    Rozsah se odvozuje z DB (nová SD se zapojí automaticky po zaškrtnutí „Lokalita sběrného dvora“
    a volitelném vyplnění skupiny v plánu svozů). IČO se nepoužívá — řidič patří ke konkrétnímu SD.
    """
    subj = (
        NameSubjectProfile.objects.filter(pk=subject_profile_id)
        .select_related("yard_settings")
        .first()
    )
    if not subj:
        return [int(subject_profile_id)]

    ordered: list[int] = []
    seen: set[int] = set()

    def add(sid: int) -> None:
        sid = int(sid)
        if sid not in seen:
            seen.add(sid)
            ordered.append(sid)

    add(subj.pk)

    grp = (subj.yard_svoz_dispatch_group or "").strip()
    if grp:
        for sid in NameSubjectProfile.objects.filter(
            yard_settings__is_collection_yard=True,
            yard_settings__yard_svoz_dispatch_group=grp,
        ).order_by("pk").values_list("pk", flat=True):
            add(sid)

    return ordered if ordered else [int(subj.pk)]
