"""AJAX validace kontejneru při založení průvodky ze sběrného dvora."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone

from catalogs.models import NameSubjectWasteSuffixPair
from catalogs.services.name_subject_pair_vehicle_kinds import pair_has_vehicle_kinds

from users.services.sberny_dvur import get_sberny_dvur_subject
from users.services.waste_doc_permissions import can_create_pruvodka
from waste_docs.services.yard_ride_container_validation import yard_ride_container_blocking_error


@login_required
def yard_ride_validate_container(request):
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Povolená je jen metoda GET."}, status=405)
    if not can_create_pruvodka(request.user):
        return JsonResponse({"ok": False, "error": "Nemáte oprávnění."}, status=403)

    subject = get_sberny_dvur_subject(request.user)
    if not subject:
        return JsonResponse({"ok": False, "error": "Chybí přiřazený subjekt sběrného dvora."}, status=400)

    pair_raw = (request.GET.get("pair_pk") or "").strip()
    if not pair_raw.isdigit():
        return JsonResponse({"ok": False, "error": "Neplatný řádek matice."}, status=400)

    rz_raw = (request.GET.get("vehicle_rz_id") or "").strip()
    if not rz_raw.isdigit():
        return JsonResponse({"ok": False, "error": "Vyberte RZ vozidla."}, status=400)

    pair = (
        NameSubjectWasteSuffixPair.objects.filter(
            pk=int(pair_raw),
            subject_profile=subject,
            yard_pruvodka_enabled=True,
        )
        .select_related("yard_vehicle_kind")
        .prefetch_related("yard_vehicle_kinds")
        .first()
    )
    if not pair or not pair_has_vehicle_kinds(pair) or not pair.effective_yard_pruvodka_activity_id():
        return JsonResponse({"ok": False, "error": "Neplatný řádek matice."}, status=400)

    container_raw = request.GET.get("container") or ""
    if not container_raw.strip():
        return JsonResponse({"ok": True, "errors": []})

    target = timezone.localdate()
    err = yard_ride_container_blocking_error(
        subject=subject,
        pair=pair,
        container_number=container_raw,
        vehicle_rz_id=int(rz_raw),
        target_date=target,
    )
    if err:
        return JsonResponse({"ok": False, "errors": [err]})
    return JsonResponse({"ok": True, "errors": []})
