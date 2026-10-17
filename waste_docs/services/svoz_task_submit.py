"""Odeslání řádku matice sběrného dvora — deduplikace otevřených požadavků na cílový den."""



from __future__ import annotations



from dataclasses import dataclass

from datetime import date



from django.contrib.auth.models import AbstractBaseUser



from catalogs.models import NameSubjectProfile

from catalogs.services.name_subject_pair_vehicle_kinds import (

    pair_vehicle_kind_ids,

    sync_pair_primary_vehicle_kind_fk,

)



from waste_docs.models import SvozTask

from waste_docs.services.svoz_dispatch import assign_driver_for_new_task

from waste_docs.services.svoz_matrix_post_collect import SvozPendingLine

from waste_docs.services.svoz_task_dedup import (
    find_done_svoz_task_for_yard_container,
    find_open_svoz_task_for_yard_container,
    yard_container_already_fulfilled_on_target,
)



__all__ = [

    "SvozSubmitResult",

    "submit_svoz_line_if_allowed",

]





@dataclass(frozen=True)

class SvozSubmitResult:

    created: bool

    skipped_duplicate: bool

    task: SvozTask | None = None

    ride_warning: str | None = None





def submit_svoz_line_if_allowed(

    pline: SvozPendingLine,

    subject: NameSubjectProfile,

    user: AbstractBaseUser,

    target_date: date,

) -> SvozSubmitResult:

    """

    Vytvoří požadavek na svoz, pokud pro stejný dvůr a kontejner na cílový den

    ještě neexistuje úkol ani aktivní jízda. Duplicitu tiše přeskočí.

    """

    if yard_container_already_fulfilled_on_target(
        subject_profile=subject,
        container_number=pline.container_numbers,
        target_date=target_date,
    ):
        existing = find_open_svoz_task_for_yard_container(
            subject_profile_id=subject.pk,
            container_number=pline.container_numbers,
            target_date=target_date,
        )
        if existing is None:
            existing = find_done_svoz_task_for_yard_container(
                subject_profile_id=subject.pk,
                container_number=pline.container_numbers,
                target_date=target_date,
            )
        return SvozSubmitResult(created=False, skipped_duplicate=True, task=existing)



    pair = pline.pair

    sync_pair_primary_vehicle_kind_fk(pair)

    kind_ids = pair_vehicle_kind_ids(pair)

    vehicle_kind_id = kind_ids[0] if kind_ids else pair.yard_vehicle_kind_id



    task = SvozTask.objects.create(

        subject_profile=subject,

        created_by=user,

        waste_type_id=pair.waste_type_id,

        suffix_id=pair.suffix_id,

        source_waste_suffix_pair=pair,

        vehicle_kind_id=vehicle_kind_id,

        activity_id=pair.yard_svoz_activity_id,

        container_numbers=pline.container_numbers,

        matrix_display_label=pline.matrix_display_label,

        yard_contact_note=pline.yard_contact_note,

        target_date=target_date,

    )

    ride_warning = assign_driver_for_new_task(task, pair, actor=user)

    return SvozSubmitResult(

        created=True,

        skipped_duplicate=False,

        task=task,

        ride_warning=ride_warning,

    )


