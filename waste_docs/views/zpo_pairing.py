"""Náhled ZPO + detail jízdy při zakládání průvodky (párování pasů)."""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair
from waste_docs.ride_pairing_detail import build_ride_detail_lines_draft
from waste_docs.yard_matrix import pruvodka_new_date_pairs_qs
from waste_docs.zpo_resolved import effective_zpo_file, zpo_kind_for_file


def _parse_positive_int(raw: str) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        v = int(raw)
    except ValueError:
        return None
    return v if v > 0 else None


def _parse_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _pair_for_zpo_draft(
    name_id: int,
    waste_type_id: int,
    suffix_id: int | None,
) -> NameSubjectWasteSuffixPair | None:
    profile = NameSubjectProfile.objects.filter(name_id=name_id).first()
    if not profile:
        return None
    pairs_qs = (
        pruvodka_new_date_pairs_qs(profile)
        .select_related("zpo", "subject_profile", "waste_type", "suffix")
        .filter(waste_type_id=waste_type_id)
        .order_by("sort_order", "id")
    )
    if suffix_id:
        candidates = list(pairs_qs.filter(suffix_id=suffix_id))
        if not candidates:
            return None
        for pair in candidates:
            if effective_zpo_file(pair):
                return pair
        return candidates[0]
    for row in pairs_qs:
        if effective_zpo_file(row):
            return row
    return None


@login_required
def zpo_pairing_draft_json(request):
    name_id = _parse_positive_int(request.GET.get("name_id", ""))
    waste_type_id = _parse_positive_int(request.GET.get("waste_type_id", ""))
    suffix_id = _parse_positive_int(request.GET.get("suffix_id", ""))

    activity_id = _parse_positive_int(request.GET.get("activity_id", ""))
    vehicle_rz_id = _parse_positive_int(request.GET.get("vehicle_rz_id", ""))
    driver_id = _parse_positive_int(request.GET.get("driver_id", ""))
    drive_date = _parse_date(request.GET.get("drive_date", ""))
    container_number = (request.GET.get("container_number") or "").strip()
    contact_phone = (request.GET.get("contact_phone") or "").strip()
    contact_note = (request.GET.get("contact_note") or "").strip()
    fulfillment_address_value = (request.GET.get("fulfillment_address_value") or "").strip()
    facility_address_display = (request.GET.get("facility_address_display") or "").strip()

    lines = build_ride_detail_lines_draft(
        name_id=name_id,
        waste_type_id=waste_type_id,
        suffix_id=suffix_id,
        activity_id=activity_id,
        vehicle_rz_id=vehicle_rz_id,
        driver_id=driver_id,
        drive_date=drive_date,
        container_number=container_number,
        contact_phone=contact_phone,
        contact_note=contact_note,
        fulfillment_address_value=fulfillment_address_value,
        facility_address_display=facility_address_display,
    )

    if not (name_id and waste_type_id):
        return JsonResponse(
            {
                "ok": True,
                "has_zpo": False,
                "reason": "incomplete_selection",
                "ride_detail_lines": lines,
            }
        )

    pair = _pair_for_zpo_draft(name_id, waste_type_id, suffix_id)

    zpo = effective_zpo_file(pair)
    if not zpo:
        return JsonResponse(
            {
                "ok": True,
                "has_zpo": False,
                "reason": "no_zpo_for_pair",
                "ride_detail_lines": lines,
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "has_zpo": True,
            "zpo_url": zpo.url,
            "zpo_kind": zpo_kind_for_file(zpo),
            "ride_detail_lines": lines,
        }
    )
