"""Sběrný dvůr — založení průvodky: matice s výběrem RZ → řidič z plánu → Pruvodka + tisk."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from catalogs.models import (
    AddressCatalog,
    DriverProfile,
    IcoCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    VehicleRzCatalog,
    WasteCodeCatalog,
    WasteCategoryCatalog,
)
from catalogs.services.fulfillment_address import normalize_fulfillment_address
from catalogs.services.name_subject_pair_vehicle_kinds import pair_vehicle_kind_ids
from catalogs.waste_catalog_code import normalize_waste_catalog_code
from users.services.sberny_dvur import get_sberny_dvur_subject
from users.services.waste_doc_permissions import can_create_pruvodka
from waste_docs.follow_up_options import has_follow_up_option
from waste_docs.models import Pruvodka
from waste_docs.services.ride_record_status import apply_pruvodka_status_after_save
from waste_docs.services.svoz_auto_container_passport import ensure_container_passport_for_svoz
from waste_docs.services.yard_ride_plan_drivers import (
    driver_allowed_for_yard_rz,
    driver_display_label,
    drivers_by_rz_for_yard_day,
    drivers_by_rz_json_map,
)
from waste_docs.services.yard_ride_container_validation import yard_ride_container_blocking_error
from waste_docs.services.yard_ride_rz_options import rz_options_for_yard_row
from waste_docs.services.yard_ride_today_created import yard_rides_today_by_pair
from waste_docs.services.weight_input import (
    format_weight_snapshot,
    parse_weight_t,
    weight_must_be_positive_error,
)
from waste_docs.yard_matrix import yard_pruvodka_matrix_rows, yard_pruvodka_matrix_stats
from waste_docs.zpo_instance_generator import ensure_zpo_instance_for_pruvodka_pk


def _split_container_numbers(raw: str) -> tuple[str, str, str]:
    text = (raw or "").replace(";", ",")
    parts = [p.strip() for p in text.split(",") if p.strip()]
    c1 = parts[0] if parts else ""
    c2 = parts[1] if len(parts) > 1 else ""
    extra = parts[2:] if len(parts) > 2 else []
    note = ("Další kontejnery: " + ", ".join(extra)) if extra else ""
    return c1, c2, note


def _resolve_address_for_pair(
    subject: NameSubjectProfile,
    pair: NameSubjectWasteSuffixPair,
) -> AddressCatalog | None:
    from catalogs.services.pair_fulfillment_address import fulfillment_address_value_for_pair

    fulfillment_val = fulfillment_address_value_for_pair(pair, subject)
    if not fulfillment_val:
        return None
    normalized = normalize_fulfillment_address(fulfillment_val)
    addr, _ = AddressCatalog.objects.get_or_create(value=normalized)
    return addr


@login_required
def yard_ride_create(request):
    if not can_create_pruvodka(request.user):
        raise Http404("Tato stránka není pro tento účet k dispozici.")
    subject = get_sberny_dvur_subject(request.user)
    if not subject:
        raise Http404("Chybí přiřazený subjekt sběrného dvora.")
    if not subject.yard_allow_pruvodka:
        messages.warning(request, "U tohoto subjektu není povoleno zakládání průvodek ze sběrného dvora.")
        return redirect(reverse("waste_docs:yard_hub"))

    rows = yard_pruvodka_matrix_rows(subject)
    matrix_stats = yard_pruvodka_matrix_stats(subject)
    errors: list[str] = []
    today = timezone.localdate()
    today_rides_by_pair = yard_rides_today_by_pair(
        subject, list(rows), today, created_by=request.user
    )

    rows_payload = [
        {
            "pair": pair,
            "rz_options": rz_options_for_yard_row(pair, subject, today),
            "today_rides": today_rides_by_pair.get(pair.pk, []),
        }
        for pair in rows
    ]
    rz_drivers_map = drivers_by_rz_json_map(subject, today)

    def _render():
        return render(
            request,
            "waste_docs/yard_ride_matrix.html",
            {
                "subject": subject,
                "rows_payload": rows_payload,
                "matrix_stats": matrix_stats,
                "errors": errors,
                "rz_drivers_map": rz_drivers_map,
                "today": today,
            },
        )

    if request.method != "POST":
        return _render()

    posted_pks = request.POST.getlist("pair_pk")

    # Najít právě jeden vyplněný řádek (RZ + kontejner)
    filled_row: dict | None = None
    filled_count = 0
    for pk_raw in posted_pks:
        if not pk_raw.isdigit():
            continue
        rz_val = (request.POST.get(f"vehicle_rz_{pk_raw}") or "").strip()
        container_val = (request.POST.get(f"container_{pk_raw}") or "").strip()
        weight_val = (request.POST.get(f"weight_{pk_raw}") or "").strip()
        if rz_val and container_val:
            filled_count += 1
            if filled_count == 1:
                filled_row = {
                    "pk_raw": pk_raw,
                    "rz_raw": rz_val,
                    "container": container_val,
                    "driver_raw": (request.POST.get(f"driver_{pk_raw}") or "").strip(),
                    "weight_raw": weight_val,
                }

    if filled_count == 0:
        errors.append("Vyplňte RZ vozidla a číslo kontejneru u jednoho řádku.")
        return _render()
    if filled_count > 1:
        errors.append("Lze založit pouze jednu průvodku najednou. Vyplňte pouze jeden řádek.")
        return _render()

    pk_raw = filled_row["pk_raw"]
    pk = int(pk_raw)
    rz_raw = filled_row["rz_raw"]
    container_number = filled_row["container"][:50]

    if not rz_raw.isdigit():
        errors.append("Vyberte RZ vozidla.")
        return _render()

    pair = (
        NameSubjectWasteSuffixPair.objects.filter(
            pk=pk, subject_profile=subject, yard_pruvodka_enabled=True,
        )
        .select_related(
            "yard_vehicle_kind",
            "yard_svoz_activity",
            "yard_pruvodka_activity",
            "waste_type",
            "suffix",
            "fulfillment_address",
        )
        .prefetch_related("yard_vehicle_kinds")
        .first()
    )
    activity_id = pair.effective_yard_pruvodka_activity_id() if pair else None
    if not pair or not activity_id:
        errors.append("Neplatný řádek odpadu — u tohoto páru není povolena průvodka z dvora nebo chybí činnost.")
        return _render()

    vehicle_rz_id = int(rz_raw)
    kind_ids = pair_vehicle_kind_ids(pair)
    vehicle_kind_id = kind_ids[0] if kind_ids else (pair.yard_vehicle_kind_id or 0)

    rz_obj = VehicleRzCatalog.objects.filter(pk=vehicle_rz_id).first()
    if not rz_obj:
        errors.append("Neplatná RZ vozidla.")
        return _render()

    container_err = yard_ride_container_blocking_error(
        subject=subject,
        pair=pair,
        container_number=container_number,
        vehicle_rz_id=vehicle_rz_id,
        target_date=today,
    )
    if container_err:
        errors.append(container_err)
        return _render()

    weight = parse_weight_t(filled_row.get("weight_raw", ""))
    weight_err = weight_must_be_positive_error(weight)
    if weight_err:
        errors.append(weight_err)
        return _render()

    driver_raw = filled_row.get("driver_raw", "")
    if not driver_raw.isdigit():
        errors.append(
            f"Vyberte řidiče přiřazeného k vozidlu na {today.strftime('%d.%m.%Y')}."
        )
        return _render()
    driver_id = int(driver_raw)
    if not driver_allowed_for_yard_rz(subject, today, vehicle_rz_id, driver_id):
        errors.append(
            f"Zvolený řidič není pro vozidlo {rz_obj.value} k dispozici "
            f"na {today.strftime('%d.%m.%Y')} (plán ani dnešní jízdy)."
        )
        return _render()

    driver_obj = DriverProfile.objects.filter(pk=driver_id).first()
    if not driver_obj:
        errors.append("Neplatný řidič.")
        return _render()

    allowed_for_rz = drivers_by_rz_for_yard_day(subject, today).get(vehicle_rz_id, [])
    if not allowed_for_rz:
        errors.append(
            f"Pro zvolenou RZ ({rz_obj.value}) není na {today.strftime('%d.%m.%Y')} "
            f"přiřazen žádný řidič (plán ani dnešní jízdy)."
        )
        return _render()

    sub = (
        NameSubjectProfile.objects.filter(pk=subject.pk)
        .select_related("name", "ico", "address_profile__fulfillment_address", "address_profile__facility_address")
        .first()
    ) or subject

    address = _resolve_address_for_pair(sub, pair)
    if not address:
        errors.append("U subjektu chybí adresa plnění/provozovny. Doplňte ji v číselníku.")
        return _render()

    ico_id = sub.ico_id
    if not ico_id:
        ico_obj, _ = IcoCatalog.objects.get_or_create(value="00000000")
        ico_id = ico_obj.pk

    c1, c2, note_extra = _split_container_numbers(container_number)
    combined_note = note_extra.strip()[:200]

    passport = None
    if c1 and vehicle_kind_id:
        passport = ensure_container_passport_for_svoz(
            c1, vehicle_kind_id=vehicle_kind_id, vehicle_kind_ids=kind_ids,
        )

    wt = pair.waste_type
    waste_code = WasteCodeCatalog.objects.filter(
        value=normalize_waste_catalog_code(wt.code) if wt.code else ""
    ).first()
    if not waste_code:
        waste_code, _ = WasteCodeCatalog.objects.get_or_create(value=wt.code or "")
    waste_cat = WasteCategoryCatalog.objects.filter(value=(wt.category or "").strip()).first()
    if not waste_cat:
        waste_cat, _ = WasteCategoryCatalog.objects.get_or_create(value=(wt.category or "").strip())

    contract = (getattr(pair, "contract_number", "") or "").strip()
    phone = (sub.contact_phone or "").strip()
    activity_obj = pair.yard_pruvodka_activity or pair.yard_svoz_activity

    with transaction.atomic():
        item = Pruvodka(
            activity_id=activity_id,
            drive_date=today,
            driver=driver_obj,
            vehicle_rz_id=vehicle_rz_id,
            container_passport=passport,
            waste_type=wt,
            waste_code=waste_code,
            waste_category=waste_cat,
            suffix=pair.suffix,
            name_id=sub.name_id,
            ico_id=ico_id,
            address=address,
            container_number=c1[:50],
            container_number_2=c2[:50],
            contact_phone=phone[:20],
            contract_number=contract[:120],
            contact_note=combined_note,
            weight_t=weight,
            weight_snapshot=format_weight_snapshot(weight),
            created_by=request.user,
            name_snapshot=(sub.name.value if sub.name_id and sub.name else ""),
            ico_snapshot=(sub.ico.value if sub.ico_id and sub.ico else ""),
            address_snapshot=address.value,
            waste_type_snapshot=wt.value if wt else "",
            waste_code_snapshot=waste_code.value if waste_code else "",
            waste_category_snapshot=waste_cat.value if waste_cat else "",
            vehicle_rz_snapshot=rz_obj.value,
            driver_snapshot=driver_display_label(driver_obj),
            contract_number_snapshot=contract[:120],
            suffix_snapshot=(pair.suffix.value if pair.suffix else ""),
            container_snapshot_2=c2[:50],
            activity_snapshot=(activity_obj.name if activity_obj else ""),
            source_waste_suffix_pair=pair,
        )
        item.follow_up_open = (
            bool(item.activity_id) and has_follow_up_option(item.activity) if item.activity_id else False
        )
        apply_pruvodka_status_after_save(item)
        item.save()
        ensure_zpo_instance_for_pruvodka_pk(item.pk)

    messages.success(request, "Průvodka založena.")
    return redirect(f"{reverse('waste_docs:yard_print_created')}?pks={item.pk}")
