from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from address_data.services import city_from_coords
from catalogs.models import IcoCatalog, NameSubjectProfile
from core.models import AppSettings


def _initial_subject_profile_id(*, yard_sub, initial: dict) -> int | None:
    if yard_sub and yard_sub.pk:
        return int(yard_sub.pk)
    name_id = initial.get("name")
    if name_id:
        pk = NameSubjectProfile.objects.filter(name_id=name_id).values_list("pk", flat=True).first()
        return int(pk) if pk else None
    return None

from users.services.sberny_dvur import (
    can_link_pruvodka_from_svoz_task,
    get_sberny_dvur_subject,
    is_sberny_dvur_role,
)
from users.services.catalog_row_visibility import effective_show_catalog_index_row
from users.services.waste_doc_permissions import can_create_pruvodka
from .helpers import build_pruvodka_copy_payload
from waste_docs.follow_up_options import has_follow_up_option, primary_follow_up_activity
from waste_docs.services.follow_up_chain import apply_parent_state_after_child_link
from waste_docs.follow_up_prefill import build_follow_up_prefill
from waste_docs.forms import PruvodkaForm
from waste_docs.models import Pruvodka, SvozTask, YardHazardousWasteRequest
from waste_docs.pruvodka_form_client import pruvodka_create_form_client_config
from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_dispatch import (
    CustomerRequestLinkError,
    can_view_customer_requests_dispatch,
    customer_requests_visible_for_dispatch,
    link_customer_request_to_pruvodka,
)
from waste_docs.services.customer_request_prefill import build_customer_request_prefill_bundle
from waste_docs.services.pruvodka_attachments import (
    apply_upload_snapshot_to_pruvodka,
    snapshot_pruvodka_form_uploads,
)
from waste_docs.services.pruvodka_day_kind_counts import ride_counts_by_vehicle_kind_bucket
from waste_docs.services.pruvodka_form_errors import flash_pruvodka_form_invalid
from waste_docs.services.ride_record_status import apply_pruvodka_status_after_save
from waste_docs.services.svoz_dispatch import svoz_dispatch_soft_warnings
from waste_docs.services.yard_hazard_request.dashboard import open_hazard_requests_for_dashboard
from waste_docs.services.yard_hazard_request.prefill import build_yard_hazard_request_prefill_bundle
from waste_docs.services.yard_hazard_request.ride_link import resolve_hazard_request_with_pruvodka
from waste_docs.services.yard_form_activity import yard_standalone_pair_hints_payload
from waste_docs.svoz_prefill import build_svoz_task_prefill_bundle
from waste_docs.svoz_task_queries import svoz_tasks_open_for_date
from waste_docs.waste_type_meta import waste_type_meta_for_pruvodka_form
from waste_docs.yard_matrix import yard_new_date_matrix_ready_qs, yard_pruvodka_initial_for_subject


@login_required
def pruvodka_create(request):
    if not can_create_pruvodka(request.user):
        messages.error(request, "Nemáte oprávnění založit novou jízdu.")
        return redirect("core:dashboard")
    date_raw = (request.GET.get("date") or "").strip()
    if not date_raw:
        date_raw = (request.session.get("dashboard_selected_date") or "").strip()
    initial = {}
    if request.method != "POST" and date_raw:
        try:
            initial["drive_date"] = date.fromisoformat(date_raw)
        except ValueError:
            pass
    follow_raw = (request.GET.get("follow_up_for") or "").strip()
    st_open_get = (request.GET.get("svoz_task") or "").strip()
    hr_open_get = (request.GET.get("yard_hazard_request") or "").strip()
    cr_open_get = (request.GET.get("customer_request") or "").strip()
    yard_sub = get_sberny_dvur_subject(request.user) if is_sberny_dvur_role(request.user) else None
    if (
        yard_sub
        and not follow_raw.isdigit()
        and not st_open_get.isdigit()
        and not hr_open_get.isdigit()
        and not cr_open_get.isdigit()
        and not yard_sub.yard_allow_pruvodka
    ):
        messages.warning(
            request,
            "U tohoto subjektu není povolena průvodka z dvora.",
        )
        return redirect("waste_docs:yard_hub")
    yard_standalone_pruvodka = bool(
        yard_sub
        and not follow_raw.isdigit()
        and not st_open_get.isdigit()
        and not hr_open_get.isdigit()
        and not cr_open_get.isdigit()
    )
    if request.method != "POST" and not follow_raw.isdigit():
        if yard_sub:
            initial.update(yard_pruvodka_initial_for_subject(yard_sub))
    parent_for_follow_up = None
    follow_up_prefill_bundle = None
    svoz_task_active_pk = None
    svoz_bundle = None
    yard_hazard_request_active_pk = None
    yard_hazard_bundle = None
    customer_request_active_pk = None
    customer_request_active = None
    customer_request_bundle = None
    if request.method != "POST" and follow_raw.isdigit():
        initial["follow_up_parent"] = int(follow_raw)
        parent_for_follow_up = (
            Pruvodka.objects.filter(pk=int(follow_raw), is_archived=False)
            .select_related(
                "activity",
                "activity__follow_up_activity",
                "ico",
                "name",
                "address",
                "waste_type",
                "suffix",
                "vehicle_rz",
                "driver",
            )
            .first()
        )
        if parent_for_follow_up and parent_for_follow_up.activity_id:
            primary = primary_follow_up_activity(parent_for_follow_up.activity)
            if primary:
                initial["activity"] = primary.pk
        if parent_for_follow_up:
            follow_up_prefill_bundle = build_follow_up_prefill(parent_for_follow_up)
            initial.update(follow_up_prefill_bundle["initial"])
    if request.method != "POST" and not follow_raw.isdigit():
        st_raw = st_open_get
        if st_raw.isdigit() and can_link_pruvodka_from_svoz_task(request.user):
            cand = (
                SvozTask.objects.filter(pk=int(st_raw), status=SvozTask.Status.OPEN)
                .select_related("vehicle_kind", "activity")
                .first()
            )
            if cand:
                if "drive_date" not in initial:
                    initial["drive_date"] = cand.target_date
                drive_cmp = initial.get("drive_date")
                if drive_cmp and cand.target_date == drive_cmp:
                    svoz_bundle = build_svoz_task_prefill_bundle(cand)
                    initial.update(svoz_bundle["initial"])
                    svoz_task_active_pk = cand.pk
                else:
                    messages.warning(
                        request,
                        "Pro úkol svozu zvolte stejné datum jízdy jako u úkolu (nebo otevřete odkaz z dashboardu).",
                    )
    if request.method != "POST" and not follow_raw.isdigit():
        hr_raw = hr_open_get
        if hr_raw.isdigit() and can_link_pruvodka_from_svoz_task(request.user):
            cand_hr = (
                YardHazardousWasteRequest.objects.filter(
                    pk=int(hr_raw),
                    status=YardHazardousWasteRequest.Status.OPEN,
                )
                .select_related("vehicle_kind", "activity")
                .first()
            )
            if cand_hr:
                yard_hazard_bundle = build_yard_hazard_request_prefill_bundle(cand_hr)
                initial.update(yard_hazard_bundle["initial"])
                yard_hazard_request_active_pk = cand_hr.pk
    if request.method != "POST" and not follow_raw.isdigit():
        cr_raw = cr_open_get
        if cr_raw.isdigit() and can_view_customer_requests_dispatch(request.user):
            cand_cr = (
                CustomerRequest.objects.filter(
                    pk=int(cr_raw),
                    status=CustomerRequest.Status.VISIBLE_FOR_DISPATCH,
                    planned_pruvodka__isnull=True,
                )
                .select_related("name", "activity", "vehicle_kind")
                .prefetch_related("activity__vehicle_kinds", "attachments")
                .first()
            )
            if cand_cr:
                if "drive_date" not in initial:
                    initial["drive_date"] = cand_cr.target_date
                drive_cmp = initial.get("drive_date")
                if drive_cmp and cand_cr.target_date == drive_cmp:
                    customer_request_bundle = build_customer_request_prefill_bundle(cand_cr)
                    initial.update(customer_request_bundle["initial"])
                    customer_request_active_pk = cand_cr.pk
                    customer_request_active = cand_cr
                else:
                    messages.warning(
                        request,
                        "Pro požadavek zvolte stejné datum jízdy jako u požadavku (nebo otevřete odkaz z dashboardu).",
                    )
    if request.method == "POST":
        yard_standalone_pruvodka = bool(
            yard_sub
            and not (request.POST.get("follow_up_parent") or "").strip().isdigit()
            and not (request.POST.get("svoz_task") or "").strip().isdigit()
            and not (request.POST.get("yard_hazard_request") or "").strip().isdigit()
            and not (request.POST.get("customer_request") or "").strip().isdigit()
        )
    if request.method != "POST" and yard_standalone_pruvodka:
        initial["drive_date"] = timezone.localdate()
    form = PruvodkaForm(
        request.POST or None,
        request.FILES or None,
        initial=initial,
        user=request.user,
        yard_standalone_mode=yard_standalone_pruvodka,
    )
    app_settings = AppSettings.load()
    if request.method == "POST" and form.is_valid():
        parent = form.cleaned_data.get("follow_up_parent")
        repeat_count = int(form.cleaned_data.get("repeat_count") or 1)
        base_item = form.save(commit=False)
        if not base_item.ico_id and base_item.name_id:
            subject = NameSubjectProfile.objects.select_related("ico").filter(name_id=base_item.name_id).first()
            if subject and subject.ico_id:
                base_item.ico_id = subject.ico_id
        if not base_item.ico_id:
            fallback_ico, _ = IcoCatalog.objects.get_or_create(value="00000000")
            base_item.ico_id = fallback_ico.pk
        copy_payload = build_pruvodka_copy_payload(base_item)
        created_items: list[Pruvodka] = []
        skip_fu = bool(form.cleaned_data.get("skip_follow_up"))
        for idx in range(repeat_count):
            item = base_item if idx == 0 else Pruvodka(**copy_payload)
            item.created_by = request.user
            if parent:
                item.follow_up_parent = parent
            item.follow_up_open = (
                bool(item.activity_id)
                and has_follow_up_option(item.activity)
                and not skip_fu
            )
            apply_pruvodka_status_after_save(item)
            item.save()
            created_items.append(item)
        first_item = created_items[0]
        upload_snapshot = snapshot_pruvodka_form_uploads(form)
        if upload_snapshot:
            for ride_saved in created_items:
                apply_upload_snapshot_to_pruvodka(ride_saved, upload_snapshot)
        if parent:
            parent_refreshed = (
                Pruvodka.objects.select_related("activity", "activity__follow_up_activity")
                .prefetch_related(
                    "activity__follow_up_activities",
                    "activity__follow_up_terminal_activities",
                )
                .filter(pk=parent.pk, is_archived=False)
                .first()
            )
            if parent_refreshed:
                apply_parent_state_after_child_link(parent_refreshed, first_item.activity_id)
        st_post = (request.POST.get("svoz_task") or "").strip()
        if st_post.isdigit() and can_link_pruvodka_from_svoz_task(request.user):
            st = SvozTask.objects.filter(pk=int(st_post), status=SvozTask.Status.OPEN).first()
            if st and st.target_date == first_item.drive_date:
                st.status = SvozTask.Status.DONE
                st.resolved_pruvodka = first_item
                st.save(update_fields=["status", "resolved_pruvodka_id"])
        hr_post = (request.POST.get("yard_hazard_request") or "").strip()
        if hr_post.isdigit() and can_link_pruvodka_from_svoz_task(request.user):
            hr = YardHazardousWasteRequest.objects.filter(
                pk=int(hr_post),
                status=YardHazardousWasteRequest.Status.OPEN,
            ).first()
            if hr:
                resolve_hazard_request_with_pruvodka(hr, first_item)
        cr_post = (request.POST.get("customer_request") or "").strip()
        if cr_post.isdigit() and can_view_customer_requests_dispatch(request.user):
            cr = CustomerRequest.objects.filter(
                pk=int(cr_post),
                planned_pruvodka__isnull=True,
            ).first()
            if cr:
                try:
                    old_target = cr.target_date
                    link_customer_request_to_pruvodka(cr, first_item, actor=request.user)
                    if old_target != first_item.drive_date:
                        messages.info(
                            request,
                            f"Požadavek #{cr.pk} propojen s jízdou; termín požadavku posunut "
                            f"na {first_item.drive_date.strftime('%d.%m.%Y')}.",
                        )
                except CustomerRequestLinkError as exc:
                    messages.warning(request, str(exc))
        if len(created_items) > 1:
            messages.success(request, f"Založeno jízd: {len(created_items)}.")
        return redirect("waste_docs:detail", pk=first_item.pk)
    if request.method == "POST" and not form.is_valid():
        flash_pruvodka_form_invalid(request, form)
    if request.method == "POST":
        raw_svoz_hidden = (request.POST.get("svoz_task") or "").strip()
        if raw_svoz_hidden.isdigit():
            svoz_task_active_pk = svoz_task_active_pk or int(raw_svoz_hidden)
        raw_hr_hidden = (request.POST.get("yard_hazard_request") or "").strip()
        if raw_hr_hidden.isdigit():
            yard_hazard_request_active_pk = yard_hazard_request_active_pk or int(raw_hr_hidden)
        raw_cr_hidden = (request.POST.get("customer_request") or "").strip()
        if raw_cr_hidden.isdigit():
            customer_request_active_pk = customer_request_active_pk or int(raw_cr_hidden)
            if customer_request_active is None:
                customer_request_active = (
                    CustomerRequest.objects.filter(pk=int(raw_cr_hidden))
                    .select_related("activity", "vehicle_kind")
                    .prefetch_related("activity__vehicle_kinds", "attachments")
                    .first()
                )
    waste_type_meta = waste_type_meta_for_pruvodka_form()
    default_city = "Česko"
    try:
        default_city = city_from_coords(float(app_settings.default_map_lat), float(app_settings.default_map_lng))
    except (TypeError, ValueError):
        default_city = "Česko"
    yard_client_payload = {"active": False}
    if yard_standalone_pruvodka and yard_sub:
        pr_pairs = list(
            yard_new_date_matrix_ready_qs(yard_sub)
            .select_related("fulfillment_address", "yard_vehicle_kind")
            .prefetch_related("yard_vehicle_kinds")
        )
        wt_ids = list(dict.fromkeys(p.waste_type_id for p in pr_pairs))
        allowed_wt_keys = {str(x) for x in wt_ids}
        waste_type_meta = {k: v for k, v in waste_type_meta.items() if k in allowed_wt_keys}
        pair_hints = yard_standalone_pair_hints_payload(yard_sub, pr_pairs)
        yard_client_payload = {
            "active": True,
            "allowedWasteTypeIds": [str(x) for x in wt_ids],
            "pairHints": pair_hints,
            "driveDateIso": timezone.localdate().isoformat(),
        }
    pruvodka_form_config = pruvodka_create_form_client_config(
        waste_type_meta=waste_type_meta,
        default_city=default_city,
        default_map_lat=app_settings.default_map_lat,
        default_map_lng=app_settings.default_map_lng,
        yard_standalone=yard_client_payload,
        can_edit_name_subject_pairs=effective_show_catalog_index_row(request.user, "name"),
        initial_subject_profile_id=_initial_subject_profile_id(yard_sub=yard_sub, initial=initial),
    )
    follow_up_pk_cfg = None
    if request.method == "POST" and form.data:
        fu = (form.data.get("follow_up_parent") or "").strip()
        if fu.isdigit():
            follow_up_pk_cfg = int(fu)
    elif initial.get("follow_up_parent") is not None:
        try:
            follow_up_pk_cfg = int(initial["follow_up_parent"])
        except (TypeError, ValueError):
            follow_up_pk_cfg = None
    pruvodka_form_config["initialFollowUpParentPk"] = follow_up_pk_cfg
    show_follow_up_banner = bool(follow_up_pk_cfg)
    if request.method != "POST" and follow_up_prefill_bundle:
        pruvodka_form_config["followUpPrefill"] = follow_up_prefill_bundle["client"]
    else:
        pruvodka_form_config["followUpPrefill"] = None
    pruvodka_form_config["svozPrefill"] = None
    if request.method != "POST" and svoz_bundle and svoz_bundle.get("client"):
        pruvodka_form_config["svozPrefill"] = svoz_bundle["client"]
    pruvodka_form_config["yardHazardPrefill"] = None
    if request.method != "POST" and yard_hazard_bundle and yard_hazard_bundle.get("client"):
        pruvodka_form_config["yardHazardPrefill"] = yard_hazard_bundle["client"]
    pruvodka_form_config["customerRequestPrefill"] = None
    if request.method != "POST" and customer_request_bundle and customer_request_bundle.get("client"):
        pruvodka_form_config["customerRequestPrefill"] = customer_request_bundle["client"]
    pruvodka_form_config["hasFormErrors"] = request.method == "POST" and bool(form.errors)
    panel_date = initial.get("drive_date")
    if panel_date is None:
        try:
            panel_date = date.fromisoformat(date_raw) if date_raw else timezone.localdate()
        except ValueError:
            panel_date = timezone.localdate()
    day_kind_counts = ride_counts_by_vehicle_kind_bucket(request.user, panel_date)
    svoz_tasks_panel = svoz_tasks_open_for_date(request.user, panel_date)
    yard_hazard_requests_panel = open_hazard_requests_for_dashboard(request.user, panel_date)
    customer_requests_panel = list(customer_requests_visible_for_dispatch(request.user, panel_date))
    can_open_svoz_task_pruvodka = can_link_pruvodka_from_svoz_task(request.user)
    can_plan_customer_requests = can_view_customer_requests_dispatch(request.user)
    return render(
        request,
        "waste_docs/form.html",
        {
            "form": form,
            "default_city": default_city,
            "pruvodka_form_config": pruvodka_form_config,
            "show_follow_up_banner": show_follow_up_banner,
            "page_title": "Nová jízda",
            "is_edit": False,
            "yard_standalone_pruvodka": yard_standalone_pruvodka,
            "svoz_task_active_pk": svoz_task_active_pk,
            "yard_hazard_request_active_pk": yard_hazard_request_active_pk,
            "customer_request_active_pk": customer_request_active_pk,
            "customer_request_active": customer_request_active,
            "day_kind_counts": day_kind_counts,
            "svoz_tasks_panel": svoz_tasks_panel,
            "yard_hazard_requests_panel": yard_hazard_requests_panel,
            "customer_requests_panel": customer_requests_panel,
            "svoz_panel_date": panel_date,
            "can_open_svoz_task_pruvodka": can_open_svoz_task_pruvodka,
            "can_plan_customer_requests": can_plan_customer_requests,
            "svoz_dispatch_warnings": svoz_dispatch_soft_warnings(request.user, panel_date),
            "can_edit_name_subject_pairs": effective_show_catalog_index_row(request.user, "name"),
        },
    )
