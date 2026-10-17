from __future__ import annotations

from waste_docs.models import Pruvodka, YardHazardousWasteRequest


def resolve_hazard_request_with_pruvodka(
    request_obj: YardHazardousWasteRequest,
    pruvodka: Pruvodka,
) -> bool:
    if request_obj.status != YardHazardousWasteRequest.Status.OPEN:
        return False
    request_obj.status = YardHazardousWasteRequest.Status.RESOLVED
    request_obj.resolved_pruvodka = pruvodka
    request_obj.save(update_fields=["status", "resolved_pruvodka_id"])
    return True
