"""Po přiřazení řidiče k otevřenému SvozTask založit průvodku a úkol označit jako vyřízený."""

from __future__ import annotations

from django.db import transaction

from catalogs.models import (
    ContainerPassport,
    DriverProfile,
    IcoCatalog,
    NameSubjectProfile,
    VehicleRzCatalog,
    VehicleRzProfile,
)
from catalogs.services.name_subject_pair_vehicle_kinds import (
    ordered_kind_ids_for_svoz_task,
    pair_for_svoz_task_record,
    pair_vehicle_kind_ids,
)
from waste_docs.follow_up_options import has_follow_up_option
from waste_docs.forms import PruvodkaForm
from waste_docs.models import Pruvodka, SvozTask
from waste_docs.services.ride_record_status import apply_pruvodka_status_after_save
from waste_docs.services.svoz_auto_container_passport import (
    _primary_container_fragment,
    ensure_container_passport_for_svoz,
    sync_container_passport_after_svoz_auto_pruvodka,
)
from waste_docs.services.svoz_auto_pruvodka_errors import (
    clear_auto_pruvodka_failure,
    label_for_skip_reason,
    pick_auto_pruvodka_fallback_actor,
    record_auto_pruvodka_failure,
)
from waste_docs.services.svoz_auto_pruvodka_skip import auto_pruvodka_skip_reason_for_svoz_task
from waste_docs.services.svoz_task_dedup import find_active_pruvodka_for_yard_container
from waste_docs.svoz_prefill import build_svoz_task_prefill_bundle
from waste_docs.zpo_instance_generator import ensure_zpo_instance_for_pruvodka_pk
from users.services.waste_doc_permissions import can_create_pruvodka


def _fail(task: SvozTask, message: str) -> tuple[bool, str]:
    return False, record_auto_pruvodka_failure(task, message)

def _pick_vehicle_rz_id_for_task(
    task: SvozTask,
    driver: DriverProfile,
    *,
    vehicle_kind_id: int,
) -> int | None:
    """RZ z profilu odpovídajícího druhu vozidla; upřednostní přiřazenou RZ řidiče."""
    if not vehicle_kind_id:
        return None
    prof_qs = VehicleRzProfile.objects.filter(vehicle_kinds__id=vehicle_kind_id).select_related("rz")
    drz_ids = list(driver.allowed_vehicle_rz.values_list("pk", flat=True))
    if drz_ids:
        prof = prof_qs.filter(pk__in=drz_ids).order_by("rz__value").first()
        if prof:
            return prof.rz_id
    prof = prof_qs.order_by("rz__value").first()
    return prof.rz_id if prof else None


def _first_form_error(form: PruvodkaForm) -> str:
    if form.non_field_errors():
        return str(form.non_field_errors()[0])
    for _field, errs in form.errors.items():
        if errs:
            return str(errs[0])
    return "Formulář průvodky není platný."


def _build_quickedit_data(task: SvozTask, vehicle_rz_id: int | None) -> dict[str, str]:
    bundle = build_svoz_task_prefill_bundle(task)
    ini = bundle["initial"]
    sub = task.subject_profile
    ico_pk = sub.ico_id
    if not ico_pk:
        ico_pk = IcoCatalog.objects.get_or_create(value="00000000")[0].pk
    data: dict[str, str] = {
        "activity": str(task.activity_id),
        "drive_date": task.target_date.isoformat(),
        "driver": str(task.assigned_driver_id),
        "waste_type": str(task.waste_type_id),
        "name": str(sub.name_id),
        "ico": str(ico_pk),
        "suffix": str(task.suffix_id),
        "container_number": (ini.get("container_number") or "")[:50],
        "container_number_2": (ini.get("container_number_2") or "")[:50],
        "contact_phone": (ini.get("contact_phone") or "")[:20],
        "contract_number": (ini.get("contract_number") or "")[:120],
        "contact_note": (ini.get("contact_note") or "")[:200],
        "fulfillment_address_value": (ini.get("fulfillment_address_value") or "").strip(),
        "repeat_count": "1",
        "skip_follow_up": "",
        "svoz_task": str(task.pk),
        "follow_up_parent": "",
        "ico_lookup": (ini.get("ico_lookup") or "")[:255],
    }
    if vehicle_rz_id:
        data["vehicle_rz"] = str(vehicle_rz_id)
    else:
        data["vehicle_rz"] = ""
    return data


def _prepare_pruvodka_form(
    st: SvozTask,
    driver: DriverProfile,
    user,
    *,
    try_kind_id: int,
    pair_kind_ids: list[int],
) -> PruvodkaForm:
    vehicle_rz_id = st.assigned_vehicle_rz_id or _pick_vehicle_rz_id_for_task(
        st, driver, vehicle_kind_id=try_kind_id
    )
    data = _build_quickedit_data(st, vehicle_rz_id)
    passport_pk: int | None = None
    c1 = (data.get("container_number") or "").strip()
    if not c1:
        c1 = _primary_container_fragment(st.container_numbers or "").strip()
    if c1:
        passport = ensure_container_passport_for_svoz(
            c1,
            vehicle_kind_id=try_kind_id,
            vehicle_kind_ids=pair_kind_ids,
        )
        if passport:
            passport_pk = passport.pk
            data["container_passport"] = str(passport_pk)

    form = PruvodkaForm(data, user=user, yard_standalone_mode=False)
    if vehicle_rz_id:
        vz_field = form.fields["vehicle_rz"]
        allowed_ids = set(vz_field.queryset.values_list("pk", flat=True))
        allowed_ids.add(vehicle_rz_id)
        vz_field.queryset = (
            VehicleRzCatalog.objects.filter(pk__in=allowed_ids).select_related("profile").distinct()
        )
    if passport_pk and "container_passport" in form.fields:
        cp_field = form.fields["container_passport"]
        allowed_cp = set(cp_field.queryset.values_list("pk", flat=True))
        allowed_cp.add(passport_pk)
        cp_field.queryset = ContainerPassport.objects.filter(pk__in=allowed_cp).select_related(
            "vehicle_kind"
        )
    form._svoz_pair_kind_ids = pair_kind_ids  # noqa: SLF001 — validace pasport × RZ pro všechny druhy páru
    return form


def try_create_pruvodka_for_assigned_svoz_task(task: SvozTask, user) -> tuple[bool, str | None]:
    """
    Z otevřeného úkolu se zadaným řidičem založí průvodku (jako ruční „Nová jízda“ z úkolu),
    úkol přepne na Vyřízeno a propojí s průvodkou.

    U sběrného dvora zkouší všechny druhy vozidla z páru subjektu — stačí, když sedí jedna kombinace
    (pasport, RZ, plán).

    Vrací (True, None) při úspěchu, (False, None) pokud autozakládání neproběhlo (bez chyby),
    (False, zpráva) při chybě validace.
    """
    ok, err = _try_create_pruvodka_with_user(task, user)
    if ok:
        return True, None

    from users.services.waste_doc_permissions import can_see_all_waste_docs

    if (
        user
        and getattr(user, "is_authenticated", False)
        and can_create_pruvodka(user)
        and not can_see_all_waste_docs(user)
    ):
        fallback = pick_auto_pruvodka_fallback_actor(user)
        if fallback is not None:
            ok2, err2 = _try_create_pruvodka_with_user(task, fallback)
            if ok2:
                return True, None
            return False, err2 or err

    return False, err


def _try_create_pruvodka_with_user(task: SvozTask, user) -> tuple[bool, str | None]:
    if not user or not user.is_authenticated:
        return False, None
    if not can_create_pruvodka(user):
        return False, None
    pk = task.pk

    with transaction.atomic():
        st = (
            SvozTask.objects.select_for_update()
            .select_related(
                "subject_profile",
                "subject_profile__name",
                "subject_profile__ico",
                "waste_type",
                "suffix",
                "vehicle_kind",
                "activity",
            )
            .filter(pk=pk)
            .first()
        )
        if not st:
            return False, None
        if st.status != SvozTask.Status.OPEN or st.resolved_pruvodka_id or not st.assigned_driver_id:
            return False, None
        if not st.activity_id:
            return _fail(st, label_for_skip_reason("no_activity"))

        driver = (
            DriverProfile.objects.prefetch_related("allowed_vehicle_rz")
            .filter(pk=st.assigned_driver_id)
            .first()
        )
        if not driver:
            return _fail(st, label_for_skip_reason("no_driver"))

        skip = auto_pruvodka_skip_reason_for_svoz_task(st)
        if skip:
            # Tichý skip pro SD (None), důvod ale uložit na dashboard.
            record_auto_pruvodka_failure(st, label_for_skip_reason(skip))
            return False, None

        if find_active_pruvodka_for_yard_container(
            subject_profile=st.subject_profile,
            container_number=st.container_numbers or "",
            drive_date=st.target_date,
        ):
            record_auto_pruvodka_failure(st, label_for_skip_reason("active_ride"))
            return False, None

        pair = pair_for_svoz_task_record(st)
        pair_kind_ids = pair_vehicle_kind_ids(pair) if pair else []
        try_kind_ids = ordered_kind_ids_for_svoz_task(st.vehicle_kind_id, pair)
        if not try_kind_ids:
            return _fail(st, label_for_skip_reason("no_vehicle_kind"))

        last_err: str | None = None
        for try_kind_id in try_kind_ids:
            form = _prepare_pruvodka_form(
                st, driver, user, try_kind_id=try_kind_id, pair_kind_ids=pair_kind_ids
            )
            try:
                valid = form.is_valid()
            except ValueError:
                last_err = "Chyba validace průvodky (neplatné pole formuláře)."
                continue
            if not valid:
                last_err = _first_form_error(form) or label_for_skip_reason("form_invalid")
                continue

            item = form.save(commit=False)
            if not item.ico_id and item.name_id:
                subject = NameSubjectProfile.objects.select_related("ico").filter(name_id=item.name_id).first()
                if subject and subject.ico_id:
                    item.ico_id = subject.ico_id
            if not item.ico_id:
                fallback_ico, _ = IcoCatalog.objects.get_or_create(value="00000000")
                item.ico_id = fallback_ico.pk
            item.created_by = user
            parent = form.cleaned_data.get("follow_up_parent")
            skip_fu = bool(form.cleaned_data.get("skip_follow_up"))
            if parent:
                item.follow_up_parent = parent
            item.follow_up_open = (
                bool(item.activity_id)
                and has_follow_up_option(item.activity)
                and not skip_fu
            )
            apply_pruvodka_status_after_save(item)
            item.save()
            sync_container_passport_after_svoz_auto_pruvodka(
                item.pk,
                vehicle_kind_id=try_kind_id,
                fallback_container_numbers=st.container_numbers or "",
            )
            ensure_zpo_instance_for_pruvodka_pk(item.pk)

            st.vehicle_kind_id = try_kind_id
            st.status = SvozTask.Status.DONE
            st.resolved_pruvodka = item
            clear_auto_pruvodka_failure(st)
            st.save(update_fields=["status", "resolved_pruvodka_id", "vehicle_kind_id"])

            return True, None

        if last_err:
            return _fail(st, last_err)
        return False, None
