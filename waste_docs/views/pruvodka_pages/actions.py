from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from users.services.access import can_see_all_waste_docs
from users.services.waste_doc_permissions import can_archive_pruvodka, can_delete_all_pruvodky
from waste_docs.views.dashboard_bulk import _can_delete_protocol_files
from waste_docs.services.ride_print_bundle_urls import ride_print_bundle_url
from waste_docs.services.bulk_print_page import build_bulk_print_config
from waste_docs.models import Pruvodka
from waste_docs.services.print_bundle_prepare import print_prepare_context
from waste_docs.services.ride_bulk_actions import (
    append_protocol_and_supplement_file_rows,
    build_print_rows_and_files,
)
from waste_docs.ride_print_service import build_ride_print_rows
from waste_docs.services.ride_print_order import order_rides_queryset
from waste_docs.services.ride_protocol_xlsx import PROTOCOL_SCOPE_GROUP, rides_for_protocol_group


@login_required
@require_POST
def pruvodka_delete_all(request):
    if not can_delete_all_pruvodky(request.user):
        raise Http404("Stránka neexistuje.")
    deleted_count, _ = Pruvodka.objects.filter(is_archived=False).delete()
    messages.success(request, f"Smazáno jízd: {deleted_count}.")
    return redirect("waste_docs:list")


@login_required
@require_POST
def pruvodka_archive(request, pk):
    item = get_object_or_404(Pruvodka.objects.select_related("activity"), pk=pk, is_archived=False)
    if not can_archive_pruvodka(request.user):
        raise Http404("Jízda neexistuje.")
    if not can_see_all_waste_docs(request.user) and item.created_by_id != request.user.id:
        raise Http404("Jízda neexistuje.")

    from waste_docs.services.ride_soft_delete import RideSoftDeleteError, soft_delete_pruvodka
    from waste_docs.services.ride_soft_delete.validation import MIN_REASON_LEN

    reason = (request.POST.get("archive_reason") or request.POST.get("reason") or "").strip()
    if len(reason) < MIN_REASON_LEN:
        return redirect("waste_docs:ride_soft_delete_confirm", pk=item.pk)

    try:
        soft_delete_pruvodka(pruvodka=item, actor=request.user, reason=reason)
    except RideSoftDeleteError as exc:
        messages.error(request, str(exc))
        return redirect("waste_docs:detail", pk=item.pk)

    messages.success(request, "Jízda byla bezpečně smazána.")
    return redirect("waste_docs:list")


@login_required
@require_POST
def pruvodka_follow_up_close(request, pk):
    item = get_object_or_404(Pruvodka, pk=pk, is_archived=False)
    if not can_see_all_waste_docs(request.user) and item.created_by_id != request.user.id:
        raise Http404("Jízda neexistuje.")
    if not item.follow_up_open:
        return redirect("waste_docs:detail", pk=item.pk)
    item.follow_up_open = False
    item.follow_up_resolved_at = timezone.now()
    item.save(update_fields=("follow_up_open", "follow_up_resolved_at"))
    messages.success(request, "Čekání na navazující jízdu bylo uzavřeno.")
    return redirect("waste_docs:detail", pk=item.pk)


@login_required
def ride_print_bundle(request):
    date_raw = (request.GET.get("date") or "").strip()
    vehicle_raw = (request.GET.get("vehicle_rz_id") or "").strip()
    try:
        selected_date = date.fromisoformat(date_raw)
        vehicle_rz_id = int(vehicle_raw)
    except (ValueError, TypeError):
        raise Http404("Neplatná jízda pro tisk.")

    pks_raw = (request.GET.get("pks") or "").strip()
    filter_pks: list[int] = []
    if pks_raw:
        try:
            filter_pks = [int(p) for p in pks_raw.split(",") if p.strip().isdigit()]
        except (ValueError, TypeError):
            raise Http404("Neplatný parametr pks.") from None
        if not filter_pks:
            raise Http404("Neplatný parametr pks.")

    driver_id: int | None = None
    driver_raw = (request.GET.get("driver_id") or "").strip()
    if driver_raw.isdigit():
        driver_id = int(driver_raw)

    from waste_docs.services.ride_bulk_actions import rides_for_print_scope

    rides = rides_for_print_scope(
        selected_date,
        request.user,
        vehicle_rz_id=vehicle_rz_id,
        filter_pks=filter_pks or None,
        driver_id=driver_id,
    )
    if not rides:
        messages.warning(
            request,
            "Pro vybranou jízdu nejsou dostupné žádné záznamy (průvodky mohou být archivované nebo je nelze zobrazit).",
        )
        return redirect(f"{reverse('core:dashboard')}?date={selected_date.isoformat()}")
    prepare_ctx = print_prepare_context(rides)
    if prepare_ctx["needs_print_prepare"]:
        print_rows = build_ride_print_rows(rides)
        file_rows = []
        zpo_warnings = []
    else:
        print_rows, file_rows, zpo_warnings = build_print_rows_and_files(rides, ensure_zpo=True)
    if zpo_warnings:
        preview = ", ".join(zpo_warnings[:8])
        extra = f" (+{len(zpo_warnings) - 8} dalších)" if len(zpo_warnings) > 8 else ""
        messages.warning(
            request,
            f"ZPO s číslem jízdy se nepodařilo vygenerovat u: {preview}{extra}. "
            "Zkontrolujte log serveru nebo obnovte stránku po opravě.",
        )
    vehicle_label = rides[0].vehicle_rz_snapshot or "—"
    driver_label = (rides[0].driver_snapshot or "").strip() or "—"
    protocol_rides = rides_for_protocol_group(
        selected_date,
        vehicle_rz_id,
        request.user,
        filter_pks=filter_pks or None,
        driver_id=driver_id,
    )
    file_rows = append_protocol_and_supplement_file_rows(
        file_rows,
        protocol_rides,
        selected_date,
        scope=PROTOCOL_SCOPE_GROUP,
        generate_if_missing=False,
    )
    return render(
        request,
        "waste_docs/ride_print_bundle.html",
        {
            "selected_date": selected_date,
            "selected_date_iso": selected_date.isoformat(),
            "vehicle_label": vehicle_label,
            "vehicle_rz_id": vehicle_rz_id,
            "driver_id": driver_id if driver_id is not None else "",
            "driver_label": driver_label,
            "print_rows": print_rows,
            "file_rows": file_rows,
            "filter_pks": filter_pks,
            "filter_pks_csv": ",".join(str(p) for p in filter_pks),
            "can_delete_protocol_files": _can_delete_protocol_files(request.user),
            "ride_print_return_url": ride_print_bundle_url(
                selected_date=selected_date,
                vehicle_rz_id=vehicle_rz_id,
                filter_pks=filter_pks,
                driver_id=driver_id,
            ),
            "bulk_print_config": build_bulk_print_config(
                selected_date_iso=selected_date.isoformat(),
                vehicle_rz_id=vehicle_rz_id,
                driver_id=driver_id,
                filter_pks=filter_pks,
            ),
            **prepare_ctx,
            "print_prepare_url": reverse("waste_docs:ride_print_bundle_prepare"),
        },
    )


@login_required
def yard_print_created(request):
    """Tisk průvodek právě vytvořených ze sběrného dvora (parametr ?pks=1,2,3)."""
    pks_raw = (request.GET.get("pks") or "").strip()
    if not pks_raw:
        raise Http404("Chybí parametr pks.")
    try:
        pks = [int(p) for p in pks_raw.split(",") if p.strip().isdigit()]
    except (ValueError, TypeError):
        raise Http404("Neplatný parametr pks.")
    if not pks:
        raise Http404("Žádné jízdy k tisku.")

    rides = list(
        order_rides_queryset(
            Pruvodka.objects.filter(pk__in=pks, is_archived=False).select_related("activity")
        )
    )
    if not rides:
        messages.warning(request, "Žádné jízdy k tisku.")
        return redirect(reverse("waste_docs:yard_hub"))

    prepare_ctx = print_prepare_context(rides)
    if prepare_ctx["needs_print_prepare"]:
        print_rows = build_ride_print_rows(rides)
        file_rows = []
        zpo_warnings = []
    else:
        print_rows, file_rows, zpo_warnings = build_print_rows_and_files(rides, ensure_zpo=True)
    if zpo_warnings:
        preview = ", ".join(zpo_warnings[:8])
        extra = f" (+{len(zpo_warnings) - 8} dalších)" if len(zpo_warnings) > 8 else ""
        messages.warning(
            request,
            f"ZPO s číslem jízdy se nepodařilo vygenerovat u: {preview}{extra}.",
        )
    selected_date = rides[0].drive_date
    vehicle_label = rides[0].vehicle_rz_snapshot or "—"
    vehicle_rz_id = rides[0].vehicle_rz_id or 0

    return render(
        request,
        "waste_docs/yard_print_created.html",
        {
            "selected_date": selected_date,
            "selected_date_iso": selected_date.isoformat(),
            "vehicle_label": vehicle_label,
            "vehicle_rz_id": vehicle_rz_id,
            "pks_csv": ",".join(str(pk) for pk in pks),
            "print_rows": print_rows,
            "file_rows": file_rows,
            "rides_count": len(rides),
            "auto_print": True,
            **prepare_ctx,
            "print_prepare_url": reverse("waste_docs:yard_print_created_prepare"),
        },
    )
