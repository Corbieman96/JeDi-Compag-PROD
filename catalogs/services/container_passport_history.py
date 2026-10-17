"""Historie pohybu kontejneru (pasportu) napříč jízdami.

Sjednocuje jízdy napojené přes FK i podle textového čísla kontejneru
(kvůli starším jízdám bez FK), včetně archivovaných, seřazené od nejnovější.
"""

from __future__ import annotations

from django.db.models import Q

from catalogs.models import ContainerPassport
from waste_docs.models import Pruvodka

HISTORY_LIMIT = 200


def container_passport_ride_history(
    passport: ContainerPassport, *, limit: int = HISTORY_LIMIT
) -> list[Pruvodka]:
    """Vrátí rozumnou historii jízd daného kontejneru (od nejnovější)."""
    number = (passport.container_number or "").strip()
    cond = Q(container_passport_id=passport.pk)
    if number:
        cond |= Q(container_number__iexact=number) | Q(container_number_2__iexact=number)
    qs = (
        Pruvodka.objects.filter(cond)
        .select_related("activity", "name", "address", "driver", "container_passport")
        .order_by("-drive_date", "-pk")
        .distinct()
    )
    return list(qs[:limit])
