from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from pio.services import effective_pio_file
from users.services.access import can_see_all_waste_docs
from users.services.waste_doc_permissions import (
    can_archive_pruvodka,
    can_create_pruvodka,
    can_edit_existing_pruvodka,
    can_view_pruvodka,
)
from waste_docs.views.access import (
    pruvodka_file_access_required,
    waste_docs_list_access_required,
)
from waste_docs.services.blank_pruvodka import is_unused_blank_pruvodka
from waste_docs.services.customer_request_for_pruvodka import (
    can_view_customer_request,
    source_customer_request_for_pruvodka,
)
from waste_docs.services.pruvodka_pair_docs import pair_docs_for_pruvodka
from waste_docs.services.zpo_instance_status import (
    explain_missing_zpo_instance,
    zpo_template_url_for_pruvodka,
)
from waste_docs.services.ride_templates import preview_vehicle_kinds_for_template_from_pruvodka
from .helpers import batch_peers_for_generated_copies
from waste_docs.services.follow_up_chain import follow_up_wait_labels
from waste_docs.models import Pruvodka
from waste_docs.ride_pairing_detail import build_ride_detail_lines_from_pruvodka
from waste_docs.services.pruvodka_generated_files import regenerate_pruvodka_excel
from waste_docs.services.reports.xlsx_to_pdf import convert_xlsx_to_pdf, print_url_for_media_rel
from waste_docs.services.ride_attachment_print import attachment_print_items_for_ride
from waste_docs.services.ride_detail_print import (
    build_detail_print_context,
    build_detail_print_file_rows,
)
from waste_docs.zpo_instance_generator import ensure_zpo_instance_for_pruvodka_pk
from waste_docs.zpo_policy import system_may_generate_zpo_instance
from waste_docs.zpo_resolved import display_zpo_file_for_pruvodka, zpo_kind_for_file


@waste_docs_list_access_required
def pruvodka_detail(request, pk):
    item = get_object_or_404(
        Pruvodka.objects.select_related(
            "activity",
            "activity__follow_up_activity",
            "container_passport",
            "container_passport__vehicle_kind",
            "vehicle_rz",
            "vehicle_rz__profile",
            "driver",
            "archived_by",
        ).prefetch_related(
            "follow_up_children",
            "attachments",
            "svoz_task_sources__created_by",
            "activity__follow_up_activities",
            "activity__follow_up_terminal_activities",
            "soft_delete_logs",
        ),
        pk=pk,
    )
    if not can_view_pruvodka(request.user, item):
        raise Http404("Jízda neexistuje.")
    if item.is_archived and not can_archive_pruvodka(request.user):
        raise Http404("Jízda neexistuje.")
    leg2_activity = item.activity.follow_up_activity if item.activity_id else None
    follow_up_terminal_names: list[str] = []
    follow_up_intermediate_names: list[str] = []
    if item.follow_up_open and item.activity_id:
        follow_up_terminal_names, follow_up_intermediate_names = follow_up_wait_labels(item.activity)
    activity_suppresses_excel = bool(item.activity and item.activity.evidence_without_excel)
    follow_up_children = list(item.follow_up_children.order_by("pk"))
    can_edit_waste_doc = can_edit_existing_pruvodka(request.user, item) and not item.is_archived
    can_create_waste_doc = can_create_pruvodka(request.user) and not item.is_archived
    ride_detail_read_only = item.is_archived or (not can_edit_waste_doc and not can_create_waste_doc)
    can_archive_waste_doc = (
        not item.is_archived
        and can_archive_pruvodka(request.user)
        and (can_see_all_waste_docs(request.user) or item.created_by_id == request.user.id)
        and not item.is_blank_pruvodka
    )
    can_archive_blank_pruvodka = (
        not item.is_archived
        and can_archive_pruvodka(request.user)
        and (can_see_all_waste_docs(request.user) or item.created_by_id == request.user.id)
        and is_unused_blank_pruvodka(item)
    )
    latest_soft_delete_log = item.soft_delete_logs.order_by("-deleted_at", "-id").first()
    may_generate_zpo = not item.is_archived and system_may_generate_zpo_instance(item)
    if may_generate_zpo and not ride_detail_read_only:
        ensure_zpo_instance_for_pruvodka_pk(item.pk)
        item.refresh_from_db()
    pair_docs = pair_docs_for_pruvodka(item)
    zpo_f = display_zpo_file_for_pruvodka(item, pair_docs)
    zpo_template_url = zpo_template_url_for_pruvodka(item, pair=pair_docs)
    zpo_missing_reason = explain_missing_zpo_instance(item, pair=pair_docs) if not zpo_f else ""
    pio_f = effective_pio_file(pair_docs)
    template_vehicle_kind_options: list = []
    template_vehicle_kind_block = ""
    if can_edit_waste_doc:
        try:
            template_vehicle_kind_options = preview_vehicle_kinds_for_template_from_pruvodka(item)
        except ValueError as exc:
            template_vehicle_kind_block = str(exc)
    pruvodka_print_url = ""
    if item.generated_file and getattr(item.generated_file, "name", None):
        pruvodka_print_url = print_url_for_media_rel(item.generated_file.name)
    detail_print = build_detail_print_context(
        item,
        request.user,
        pruvodka_print_url=pruvodka_print_url,
        read_only=ride_detail_read_only,
    )
    detail_print["file_rows"] = build_detail_print_file_rows(item, request.user)
    pruvodka_pdf_url = detail_print["urls"]["pruvodka_pdf"]
    source_customer_request = None
    linked_cr = source_customer_request_for_pruvodka(item)
    if linked_cr and can_view_customer_request(request.user, linked_cr):
        source_customer_request = linked_cr
    return render(
        request,
        "waste_docs/detail.html",
        {
            "item": item,
            "pair_docs": pair_docs,
            "effective_zpo_url": zpo_f.url if zpo_f else "",
            "effective_zpo_kind": zpo_kind_for_file(zpo_f) if zpo_f else "",
            "effective_pio_url": pio_f.url if pio_f else "",
            "leg2_activity": leg2_activity,
            "follow_up_terminal_names": follow_up_terminal_names,
            "follow_up_intermediate_names": follow_up_intermediate_names,
            "activity_suppresses_excel": activity_suppresses_excel,
            "follow_up_children": follow_up_children,
            "can_edit_waste_doc": can_edit_waste_doc,
            "can_create_waste_doc": can_create_waste_doc,
            "ride_detail_read_only": ride_detail_read_only,
            "can_archive_waste_doc": can_archive_waste_doc,
            "can_archive_blank_pruvodka": can_archive_blank_pruvodka,
            "ride_is_archived": item.is_archived,
            "latest_soft_delete_log": latest_soft_delete_log,
            "may_generate_zpo": may_generate_zpo,
            "zpo_template_url": zpo_template_url,
            "zpo_missing_reason": zpo_missing_reason,
            "template_vehicle_kind_options": template_vehicle_kind_options,
            "template_vehicle_kind_block": template_vehicle_kind_block,
            "pruvodka_print_url": pruvodka_print_url,
            "pruvodka_pdf_url": pruvodka_pdf_url,
            "detail_print": detail_print,
            "open_print_after_generate": (request.GET.get("open_print") or "").strip() == "1",
            "ride_attachment_print_items": attachment_print_items_for_ride(item),
            "source_customer_request": source_customer_request,
        },
    )


@login_required
@require_POST
def pruvodka_generate(request, pk):
    item = get_object_or_404(Pruvodka.objects.select_related("activity"), pk=pk, is_archived=False)
    if not can_view_pruvodka(request.user, item):
        raise Http404("Jízda neexistuje.")
    if not can_edit_existing_pruvodka(request.user, item) and not can_create_pruvodka(request.user):
        raise Http404("Jízda neexistuje.")
    if item.activity and item.activity.evidence_without_excel:
        messages.error(
            request,
            "U této činnosti není generování Excelu k dispozici (evidence pouze v databázi).",
        )
        return redirect("waste_docs:detail", pk=item.pk)
    peers = list(batch_peers_for_generated_copies(item))
    generated_count = 0
    for ride in peers:
        if ride.activity and ride.activity.evidence_without_excel:
            continue
        if regenerate_pruvodka_excel(ride) is not None:
            generated_count += 1
        ensure_zpo_instance_for_pruvodka_pk(ride.pk, force=True)
    if generated_count > 1:
        messages.success(request, f"Přegenerováno průvodek: {generated_count}.")
    pair_docs = pair_docs_for_pruvodka(item)
    item.refresh_from_db()
    if display_zpo_file_for_pruvodka(item, pair_docs):
        return redirect("waste_docs:zpo_preview", pk=item.pk)
    return redirect(f"{reverse('waste_docs:detail', kwargs={'pk': item.pk})}?open_print=1")


@waste_docs_list_access_required
def pruvodka_zpo_preview(request, pk):
    item = get_object_or_404(Pruvodka, pk=pk, is_archived=False)
    if not can_view_pruvodka(request.user, item):
        raise Http404("Jízda neexistuje.")
    pair_docs = pair_docs_for_pruvodka(item)
    read_only = not can_edit_existing_pruvodka(request.user, item) and not can_create_pruvodka(
        request.user
    )
    if not read_only:
        ensure_zpo_instance_for_pruvodka_pk(item.pk)
        item.refresh_from_db()
    zpo_f = display_zpo_file_for_pruvodka(item, pair_docs)
    if not zpo_f:
        return redirect("waste_docs:detail", pk=item.pk)
    zpo_kind = zpo_kind_for_file(zpo_f)
    pio_f = effective_pio_file(pair_docs)
    ride_detail_lines = build_ride_detail_lines_from_pruvodka(item)
    return render(
        request,
        "waste_docs/zpo_preview.html",
        {
            "item": item,
            "pair_docs": pair_docs,
            "zpo_url": zpo_f.url,
            "zpo_kind": zpo_kind,
            "effective_pio_url": pio_f.url if pio_f else "",
            "ride_detail_lines": ride_detail_lines,
        },
    )


@pruvodka_file_access_required
def ride_pruvodka_pdf(request, pk):
    item = get_object_or_404(Pruvodka.objects.select_related("activity"), pk=pk, is_archived=False)
    if not can_view_pruvodka(request.user, item):
        raise Http404("Jízda neexistuje.")
    if item.activity and item.activity.evidence_without_excel:
        raise Http404("U této činnosti se Excel negeneruje.")
    read_only = not can_edit_existing_pruvodka(request.user, item) and not can_create_pruvodka(
        request.user
    )
    if read_only:
        if not item.generated_file:
            raise Http404("Průvodka zatím není k dispozici.")
    else:
        path = regenerate_pruvodka_excel(item)
        if path is None:
            raise Http404("Průvodku nelze vygenerovat.")
        item.refresh_from_db()
    media_rel = item.generated_file.name.replace("\\", "/").lstrip("/")
    try:
        pdf_path = convert_xlsx_to_pdf(
            Path(settings.MEDIA_ROOT) / media_rel,
            media_rel=media_rel,
        )
    except Exception as exc:
        raise Http404(f"Průvodku nelze převést na PDF: {exc}") from exc
    return FileResponse(
        pdf_path.open("rb"),
        content_type="application/pdf",
        filename=pdf_path.name,
    )


@pruvodka_file_access_required
def pruvodka_download(request, pk):
    item = get_object_or_404(Pruvodka.objects.select_related("activity"), pk=pk, is_archived=False)
    if not can_view_pruvodka(request.user, item):
        raise Http404("Jízda neexistuje.")
    if item.activity and item.activity.evidence_without_excel:
        raise Http404("U této činnosti se Excel negeneruje.")
    read_only = not can_edit_existing_pruvodka(request.user, item) and not can_create_pruvodka(
        request.user
    )
    if read_only:
        if not item.generated_file:
            raise Http404("Průvodka zatím není k dispozici.")
    else:
        path = regenerate_pruvodka_excel(item)
        if path is None:
            raise Http404("Průvodku nelze vygenerovat.")
        item.refresh_from_db()
    return FileResponse(
        item.generated_file.open("rb"),
        as_attachment=True,
        filename=Path(item.generated_file.name).name,
    )
