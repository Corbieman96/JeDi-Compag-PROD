from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.http import JsonResponse

from catalogs.models import (
    ActivityCatalog,
    DriverProfile,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    VehicleKindCatalog,
    VehicleRzProfile,
)
from catalogs.services.vehicle_kind_compatibility import vehicle_kinds_covering_task
from catalogs.services.driver_absence import driver_ids_fully_absent_on_date
from catalogs.services.name_subject_pruvodka_snapshot import subject_snapshot_for_pruvodka
from .helpers import normalize_search_text, subject_search_blob
from waste_docs.suffix_by_context import suffixes_by_context_payload


@login_required
def subject_search(request):
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"ok": True, "data": []})

    nitro_only = False
    activity_raw = (request.GET.get("activity_id") or "").strip()
    if activity_raw.isdigit():
        nitro_only = ActivityCatalog.objects.filter(
            pk=int(activity_raw),
            require_nitropodnikovy_subjekt=True,
        ).exists()

    pair_qs = NameSubjectWasteSuffixPair.objects.select_related(
        "waste_type", "yard_vehicle_kind", "fulfillment_address"
    ).prefetch_related("yard_vehicle_kinds")
    qs = (
        NameSubjectProfile.objects.select_related(
            "name",
            "ico",
            "address_profile__facility_address",
            "address_profile__fulfillment_address",
        )
        .prefetch_related(
            Prefetch("waste_suffix_pairs", queryset=pair_qs),
            "allowed_waste_types",
        )
        .filter(
            Q(ico__value__icontains=query)
            | Q(name__value__icontains=query)
            | Q(company_name__icontains=query)
        )
    )
    if nitro_only:
        qs = qs.filter(nitropodnikovy_subjekt=True, is_municipality=False)
    items = list(qs[:20])
    if query and not items:
        q_norm = normalize_search_text(query)
        fallback_qs = (
            NameSubjectProfile.objects.select_related(
                "name",
                "ico",
                "address_profile__facility_address",
                "address_profile__fulfillment_address",
            )
            .prefetch_related(
                Prefetch("waste_suffix_pairs", queryset=pair_qs),
                "allowed_waste_types",
            )
        )
        if nitro_only:
            fallback_qs = fallback_qs.filter(nitropodnikovy_subjekt=True, is_municipality=False)
        matched = []
        for row in fallback_qs[:1200]:
            if q_norm in normalize_search_text(subject_search_blob(row)):
                matched.append(row)
            if len(matched) >= 20:
                break
        items = matched
    data = [subject_snapshot_for_pruvodka(item) for item in items]
    return JsonResponse({"ok": True, "data": data})


@login_required
def vehicle_rz_by_activity(request):
    activity_raw = (request.GET.get("activity_id") or "").strip()
    try:
        activity_id = int(activity_raw)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Neplatná činnost."}, status=400)

    required_kind_raw = (request.GET.get("required_vehicle_kind_id") or "").strip()
    covering_kind_ids: list[int] | None = None
    if required_kind_raw:
        try:
            required_kind_id = int(required_kind_raw)
        except ValueError:
            return JsonResponse({"ok": False, "error": "Neplatný požadovaný druh vozidla."}, status=400)
        covering_kind_ids = sorted(vehicle_kinds_covering_task(required_kind_id))

    items = (
        VehicleRzProfile.objects.select_related("rz")
        .filter(vehicle_kinds__activities__id=activity_id)
        .distinct()
        .order_by("rz__value")
    )
    if covering_kind_ids is not None:
        items = items.filter(vehicle_kinds__id__in=covering_kind_ids).distinct()
    data = []
    for item in items:
        note = (item.vehicle_type or "").strip()
        kinds = ", ".join(
            item.vehicle_kinds.exclude(shortcut="").values_list("shortcut", flat=True).distinct()
        )
        details = " | ".join(part for part in [note, f"Druh: {kinds}" if kinds else ""] if part)
        label = f"{item.rz.value} - {details}" if details else item.rz.value
        kind_ids = list(item.vehicle_kinds.values_list("id", flat=True))
        data.append({"id": item.rz_id, "label": label, "kind_ids": kind_ids})
    return JsonResponse({"ok": True, "data": data})


@login_required
def drivers_by_context(request):
    activity_raw = (request.GET.get("activity_id") or "").strip()
    if not activity_raw:
        return JsonResponse({"ok": True, "data": []})
    try:
        activity_id = int(activity_raw)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Neplatná činnost."}, status=400)

    q = (request.GET.get("q") or "").strip()
    drive_raw = (request.GET.get("drive_date") or "").strip()
    required_kind_raw = (request.GET.get("required_vehicle_kind_id") or "").strip()
    drive_date = None
    if drive_raw:
        try:
            drive_date = datetime.strptime(drive_raw, "%Y-%m-%d").date()
        except ValueError:
            drive_date = None

    drivers = (
        DriverProfile.objects.filter(
            Q(allowed_vehicle_kinds__activities__id=activity_id)
            | Q(allowed_vehicle_rz__vehicle_kinds__activities__id=activity_id)
        )
        .distinct()
        .prefetch_related("allowed_vehicle_rz__rz", "allowed_vehicle_kinds")
    )
    if required_kind_raw:
        try:
            required_kind_id = int(required_kind_raw)
        except ValueError:
            return JsonResponse({"ok": False, "error": "Neplatný požadovaný druh vozidla."}, status=400)
        covering = list(vehicle_kinds_covering_task(required_kind_id))
        drivers = drivers.filter(
            Q(allowed_vehicle_kinds__id__in=covering)
            | Q(allowed_vehicle_rz__vehicle_kinds__id__in=covering)
        )
    if drive_date:
        drivers = drivers.exclude(pk__in=driver_ids_fully_absent_on_date(drive_date))
    if q:
        drivers = drivers.filter(
            Q(last_name__icontains=q)
            | Q(first_name__icontains=q)
            | Q(personal_number__icontains=q)
            | Q(title__icontains=q)
        )
    drivers = drivers.order_by("last_name", "first_name", "personal_number")

    data = []
    for item in drivers:
        full_name = " ".join(part for part in [item.last_name, item.first_name] if part).strip() or item.personal_number
        personal_number = (item.personal_number or "").strip()
        rz_profiles = list(
            item.allowed_vehicle_rz.filter(vehicle_kinds__activities__id=activity_id).distinct()
        )
        rz_labels = []
        for profile in rz_profiles:
            note = (profile.vehicle_type or "").strip()
            rz_labels.append(f"{profile.rz.value}{' - ' + note if note else ''}")
        kind_id_set = set(
            item.allowed_vehicle_kinds.filter(activities__id=activity_id).values_list("id", flat=True)
        )
        for profile in rz_profiles:
            kind_id_set.update(
                profile.vehicle_kinds.filter(activities__id=activity_id).values_list("id", flat=True)
            )
        kind_ids = sorted(kind_id_set)
        kinds = list(
            VehicleKindCatalog.objects.filter(pk__in=kind_id_set)
            .exclude(shortcut="")
            .order_by("shortcut")
            .values_list("shortcut", flat=True)
        )
        rz_ids = [profile.rz_id for profile in rz_profiles]
        label = full_name
        if personal_number and personal_number not in label:
            label = f"{label} ({personal_number})"
        data.append(
            {
                "id": item.pk,
                "label": label,
                "rz_text": ", ".join(rz_labels),
                "kinds_text": ", ".join(kinds),
                "rz_ids": rz_ids,
                "kind_ids": kind_ids,
            }
        )
    return JsonResponse({"ok": True, "data": data})


@login_required
def suffixes_by_context(request):
    return JsonResponse(suffixes_by_context_payload(request.GET))
