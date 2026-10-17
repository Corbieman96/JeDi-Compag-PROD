"""Tiché důvody, proč se ze SvozTask nezakládá automatická průvodka."""



from __future__ import annotations



from catalogs.services.name_subject_pair_vehicle_kinds import pair_for_svoz_task_record

from waste_docs.models import SvozTask





def auto_pruvodka_skip_reason_for_svoz_task(task: SvozTask) -> str | None:

    """

    Vrátí interní důvod skipu auto-založení jízdy, nebo None pokud lze pokračovat.



    Výsledek se nezobrazuje uživateli sběrného dvora — požadavek zůstane OPEN na dashboardu.

    """

    from waste_docs.services.svoz_dispatch.matrix_plan_match import (

        matrix_pair_resolves_to_plan_assignment,

    )



    pair = pair_for_svoz_task_record(task)

    if not pair:

        return "no_pair"



    subject = task.subject_profile

    if not matrix_pair_resolves_to_plan_assignment(subject, pair, task.target_date):

        return "no_plan"



    return None


