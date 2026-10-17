from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from address_data.services import city_from_coords
from core.models import AppSettings
from users.services.access import can_see_all_waste_docs
from users.services.waste_doc_permissions import can_edit_existing_pruvodka
from waste_docs.follow_up_options import has_follow_up_option
from waste_docs.services.follow_up_chain import sync_parent_follow_up_open_state
from waste_docs.follow_up_prefill import build_edit_form_prefill_bundle
from waste_docs.forms import PruvodkaForm
from waste_docs.models import Pruvodka
from users.services.catalog_row_visibility import effective_show_catalog_index_row
from catalogs.models import NameSubjectProfile
from waste_docs.pruvodka_form_client import pruvodka_create_form_client_config
from waste_docs.services.pruvodka_attachments import (
    append_upload_snapshot_to_pruvodka,
    snapshot_pruvodka_form_uploads,
)
from waste_docs.services.pruvodka_form_errors import flash_pruvodka_form_invalid
from waste_docs.services.ride_record_status import apply_pruvodka_status_after_save
from waste_docs.waste_type_meta import waste_type_meta_for_pruvodka_form


@login_required
def pruvodka_edit(request, pk):
    item = get_object_or_404(
        Pruvodka.objects.select_related(
            "activity",
            "activity__follow_up_activity",
            "waste_type",
            "ico",
            "name",
            "address",
            "suffix",
            "vehicle_rz",
            "container_passport",
            "container_passport__vehicle_kind",
            "driver",
        ).prefetch_related("attachments"),
        pk=pk,
        is_archived=False,
    )
    if not can_see_all_waste_docs(request.user) and item.created_by_id != request.user.id:
        raise Http404("Jízda neexistuje.")
    if not can_edit_existing_pruvodka(request.user, item):
        raise Http404("Jízda neexistuje.")

    edit_bundle = build_edit_form_prefill_bundle(item)
    form = PruvodkaForm(
        request.POST or None,
        request.FILES or None,
        instance=item,
        initial=edit_bundle["initial"],
        is_edit=True,
        user=request.user,
    )
    app_settings = AppSettings.load()
    if request.method == "POST" and form.is_valid():
        old_parent_id = item.follow_up_parent_id
        obj = form.save(commit=False)
        obj.created_by = item.created_by
        from waste_docs.services.blank_pruvodka import maybe_clear_blank_flag

        maybe_clear_blank_flag(obj)
        new_parent_id = obj.follow_up_parent_id
        skip_fu = bool(form.cleaned_data.get("skip_follow_up"))
        obj.follow_up_open = (
            bool(obj.activity_id)
            and has_follow_up_option(obj.activity)
            and not skip_fu
        )
        apply_pruvodka_status_after_save(obj)
        obj.save()

        from waste_docs.services.pruvodka_pair_docs import pair_docs_for_pruvodka
        from waste_docs.services.zpo_instance_status import explain_missing_zpo_instance
        from waste_docs.zpo_instance_generator import ensure_zpo_instance_for_pruvodka_pk
        from waste_docs.zpo_policy import system_may_generate_zpo_instance
        from waste_docs.zpo_resolved import display_zpo_file_for_pruvodka

        if system_may_generate_zpo_instance(obj) and (obj.snd_cislo_listu or "").strip():
            ensure_zpo_instance_for_pruvodka_pk(obj.pk)
            obj.refresh_from_db()
            if not display_zpo_file_for_pruvodka(obj, pair_docs_for_pruvodka(obj)):
                reason = explain_missing_zpo_instance(obj)
                if reason:
                    messages.warning(
                        request,
                        f"ZPO s číslem listu se nepodařilo připravit: {reason}",
                    )

        upload_snapshot = snapshot_pruvodka_form_uploads(form)
        if upload_snapshot:
            append_upload_snapshot_to_pruvodka(obj, upload_snapshot)

        touched_parent_ids = {pid for pid in (old_parent_id, new_parent_id) if pid}
        if touched_parent_ids:
            parents = Pruvodka.objects.select_related(
                "activity",
                "activity__follow_up_activity",
            ).prefetch_related(
                "activity__follow_up_activities",
                "activity__follow_up_terminal_activities",
            ).filter(pk__in=touched_parent_ids)
            for parent in parents:
                sync_parent_follow_up_open_state(parent)

        messages.success(request, "Jízda byla uložena.")
        return redirect("waste_docs:detail", pk=item.pk)

    if request.method == "POST" and not form.is_valid():
        flash_pruvodka_form_invalid(request, form)

    waste_type_meta = waste_type_meta_for_pruvodka_form()
    default_city = "Česko"
    try:
        default_city = city_from_coords(float(app_settings.default_map_lat), float(app_settings.default_map_lng))
    except (TypeError, ValueError):
        default_city = "Česko"
    edit_subject_profile_id = None
    if item.name_id:
        edit_pk = NameSubjectProfile.objects.filter(name_id=item.name_id).values_list("pk", flat=True).first()
        edit_subject_profile_id = int(edit_pk) if edit_pk else None
    pruvodka_form_config = pruvodka_create_form_client_config(
        waste_type_meta=waste_type_meta,
        default_city=default_city,
        default_map_lat=app_settings.default_map_lat,
        default_map_lng=app_settings.default_map_lng,
        can_edit_name_subject_pairs=effective_show_catalog_index_row(request.user, "name"),
        initial_subject_profile_id=edit_subject_profile_id,
    )
    follow_up_pk_cfg = None
    if request.method == "POST" and form.data:
        fu = (form.data.get("follow_up_parent") or "").strip()
        if fu.isdigit():
            follow_up_pk_cfg = int(fu)
    elif item.follow_up_parent_id:
        follow_up_pk_cfg = item.follow_up_parent_id
    pruvodka_form_config["initialFollowUpParentPk"] = follow_up_pk_cfg
    pruvodka_form_config["followUpPrefill"] = None
    pruvodka_form_config["svozPrefill"] = None
    pruvodka_form_config["isEdit"] = True
    pruvodka_form_config["editItemPk"] = item.pk
    pruvodka_form_config["editFormPrefill"] = edit_bundle["client"]
    pruvodka_form_config["hasFormErrors"] = request.method == "POST" and bool(form.errors)

    return render(
        request,
        "waste_docs/form.html",
        {
            "form": form,
            "default_city": default_city,
            "pruvodka_form_config": pruvodka_form_config,
            "show_follow_up_banner": bool(follow_up_pk_cfg),
            "page_title": "Upravit jízdu",
            "is_edit": True,
            "yard_standalone_pruvodka": False,
            "form_intro": "Údaje odpovídají uložené jízdě. Upravte je a uložte.",
            "is_blank_pruvodka": item.is_blank_pruvodka,
            "svoz_task_active_pk": None,
            "svoz_tasks_panel": [],
            "svoz_panel_date": None,
            "can_open_svoz_task_pruvodka": False,
            "svoz_dispatch_warnings": [],
            "can_edit_name_subject_pairs": effective_show_catalog_index_row(request.user, "name"),
        },
    )
