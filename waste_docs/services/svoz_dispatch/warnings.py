"""Měkká upozornění na dashboardu / u nové jízdy."""

from __future__ import annotations

from users.services.access import can_see_all_waste_docs
from waste_docs.models import SvozTask


def svoz_dispatch_soft_warnings(user, day) -> list[str]:
    if not user.is_authenticated or not can_see_all_waste_docs(user):
        return []
    if not SvozTask.objects.filter(
        target_date=day,
        status=SvozTask.Status.OPEN,
        assigned_driver__isnull=True,
    ).exists():
        return []
    return [
        "Některé otevřené požadavky na svoz nemají přiřazeného řidiče. "
        "Doplňte plán svozů na tento den (datum realizace) nebo přiřaďte řidiče u jednotlivých řádků."
    ]
