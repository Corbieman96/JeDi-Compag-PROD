"""AJAX validace kontejneru v matici požadavku (pasport × plán) — online při psaní."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from catalogs.models import NameSubjectWasteSuffixPair

from users.services.sberny_dvur import can_create_svoz_request, get_sberny_dvur_subject
from waste_docs.services.container_passport_ride_validation import normalize_container_number
from waste_docs.services.svoz_dispatch.exception_slot import matrix_pair_display_label
from waste_docs.services.svoz_matrix_container_validation import (
    matrix_container_passport_errors_for_field,
    matrix_unknown_passport_log_message,
    matrix_unknown_passport_numbers_for_field,
)
from waste_docs.services.svoz_matrix_submit_error_log import record_live_validation_errors
from waste_docs.svoz_schedule import next_svoz_target_date


@login_required
def svoz_matrix_validate_container(request):
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Povolená je jen metoda GET."}, status=405)
    if not can_create_svoz_request(request.user):
        return JsonResponse({"ok": False, "error": "Nemáte oprávnění."}, status=403)

    subject = get_sberny_dvur_subject(request.user)
    if not subject:
        return JsonResponse({"ok": False, "error": "Chybí přiřazený subjekt sběrného dvora."}, status=400)

    pair_raw = (request.GET.get("pair_pk") or "").strip()
    if not pair_raw.isdigit():
        return JsonResponse({"ok": False, "error": "Neplatný řádek matice."}, status=400)

    pair = (
        NameSubjectWasteSuffixPair.objects.filter(
            pk=int(pair_raw),
            subject_profile=subject,
            yard_svoz_enabled=True,
        )
        .select_related("yard_vehicle_kind")
        .prefetch_related("yard_vehicle_kinds")
        .first()
    )
    from catalogs.services.name_subject_pair_vehicle_kinds import pair_has_vehicle_kinds

    if not pair or not pair_has_vehicle_kinds(pair) or not pair.yard_svoz_activity_id:
        return JsonResponse({"ok": False, "error": "Neplatný řádek matice."}, status=400)

    containers_raw = request.GET.get("containers") or ""
    display_label = matrix_pair_display_label(pair)

    if request.GET.get("confirm_rejected") == "1":
        num = normalize_container_number(request.GET.get("rejected_number") or containers_raw)
        if num:
            record_live_validation_errors(
                subject=subject,
                user=request.user,
                messages=[
                    f"Odmítnuto potvrzení čísla kontejneru {num} při odeslání hlášení "
                    f"(obsluha zvolila Ne — hlášení neodesláno)."
                ],
                display_label=display_label,
                container_numbers=num,
            )
        return JsonResponse({"ok": True, "errors": [], "unknown_numbers": []})

    if request.GET.get("confirm_accepted") == "1":
        num = normalize_container_number(request.GET.get("accepted_number") or containers_raw)
        if num:
            who = (request.user.get_full_name() or "").strip() or request.user.get_username()
            record_live_validation_errors(
                subject=subject,
                user=request.user,
                messages=[
                    f"Potvrzeno číslo mimo číselník {num} — potvrdil: {who}."
                ],
                display_label=display_label,
                container_numbers=num,
            )
        return JsonResponse({"ok": True, "errors": [], "unknown_numbers": []})

    if not containers_raw.strip():
        return JsonResponse({"ok": True, "errors": [], "unknown_numbers": []})

    target = next_svoz_target_date()
    errors = matrix_container_passport_errors_for_field(
        subject=subject,
        pair=pair,
        container_field_raw=containers_raw,
        target_date=target,
    )
    unknown_numbers = matrix_unknown_passport_numbers_for_field(
        pair=pair,
        container_field_raw=containers_raw,
    )
    if unknown_numbers:
        record_live_validation_errors(
            subject=subject,
            user=request.user,
            messages=[
                matrix_unknown_passport_log_message(pair=pair, num=n) for n in unknown_numbers
            ],
            display_label=display_label,
            container_numbers=containers_raw,
        )
    if errors:
        record_live_validation_errors(
            subject=subject,
            user=request.user,
            messages=errors,
            display_label=display_label,
            container_numbers=containers_raw,
        )
        return JsonResponse({"ok": False, "errors": errors, "unknown_numbers": unknown_numbers})
    return JsonResponse({"ok": True, "errors": [], "unknown_numbers": unknown_numbers})
