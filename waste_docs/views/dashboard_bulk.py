from __future__ import annotations

from datetime import date
from pathlib import Path

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from users.services.access import can_see_all_waste_docs
from waste_docs.services.bulk_print_page import build_bulk_print_config
from waste_docs.services.manual_print_marks import (
    clear_protocol_marks_for_date,
    migrate_legacy_protocol_marks,
    printed_row_keys,
)
from waste_docs.services.print_bundle_prepare import print_prepare_context
from waste_docs.services.pruvodka_generated_files import regenerate_all_excels
from waste_docs.services.ride_bulk_actions import (
    append_day_protocol_file,
    build_print_rows_and_files,
    delete_protocol_files_for_rides,
    rides_for_day,
)
from waste_docs.ride_print_service import build_ride_print_rows
from waste_docs.services.reports.protocol_plan_slots import plan_only_protocol_slots
from waste_docs.services.ride_protocol_xlsx import PROTOCOL_SCOPE_DAY, rides_for_protocol_day


def _parse_date_or_404(raw: str) -> date:
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError as exc:
        raise Http404("Neplatné datum.") from exc


def _can_delete_protocol_files(user) -> bool:
    return bool(user.is_authenticated and can_see_all_waste_docs(user))


@login_required
@require_POST
def dashboard_bulk_generate_protocol(request):
    selected_date = _parse_date_or_404(request.POST.get("date") or "")
    dashboard_bulk_url = f"{reverse('waste_docs:dashboard_bulk_print')}?date={selected_date.isoformat()}"
    rides = rides_for_protocol_day(selected_date, request.user)
    plan_slots = plan_only_protocol_slots(selected_date)
    if not rides and not plan_slots:
        messages.warning(request, "Pro vybraný den nejsou dostupné žádné jízdy ani sloty plánu svozů.")
        return redirect(dashboard_bulk_url)
    file_rows: list[dict] = []
    before_count = len(file_rows)
    file_rows = append_day_protocol_file(
        file_rows,
        rides,
        selected_date,
        force_regenerate=True,
    )
    if len(file_rows) > before_count:
        clear_protocol_marks_for_date(selected_date)
        messages.success(request, "PDF protokol byl vygenerován.")
    else:
        messages.warning(request, "Protokol se nepodařilo vygenerovat.")
    return redirect(dashboard_bulk_url)


@login_required
@require_POST
def dashboard_bulk_generate(request):
    selected_date = _parse_date_or_404(request.POST.get("date") or "")
    dashboard_url = f"{reverse('core:dashboard')}?date={selected_date.isoformat()}"
    rides = rides_for_day(selected_date, request.user)
    if not rides:
        messages.warning(request, "Pro vybraný den nejsou dostupné žádné jízdy.")
        return redirect(dashboard_url)
    generated_count = regenerate_all_excels(rides)
    if generated_count:
        messages.success(request, f"Přegenerováno průvodek: {generated_count}.")
    else:
        messages.info(request, "Nebyla nalezena žádná jízda s Excel průvodkou (u činností bez Excelu se negeneruje).")
    return redirect(dashboard_url)


@login_required
def dashboard_bulk_print(request):
    selected_date = _parse_date_or_404(request.GET.get("date") or "")
    dashboard_url = f"{reverse('core:dashboard')}?date={selected_date.isoformat()}"
    rides = rides_for_day(selected_date, request.user)
    if not rides:
        messages.warning(request, "Pro vybraný den nejsou dostupné žádné jízdy.")
        return redirect(dashboard_url)
    prepare_ctx = print_prepare_context(rides)
    if prepare_ctx["needs_print_prepare"]:
        print_rows = build_ride_print_rows(rides)
        file_rows = []
    else:
        print_rows, file_rows, _zpo_warnings = build_print_rows_and_files(rides, include_pio=False, ensure_zpo=True)
    protocol_rides = rides_for_protocol_day(selected_date, request.user)
    file_rows = append_day_protocol_file(
        file_rows,
        protocol_rides,
        selected_date,
        generate_if_missing=False,
        regenerate_if_stale=True,
    )
    migrate_legacy_protocol_marks(request.user, selected_date)
    return render(
        request,
        "waste_docs/ride_print_bundle.html",
        {
            "selected_date": selected_date,
            "selected_date_iso": selected_date.isoformat(),
            "vehicle_label": "Všechny RZ",
            "vehicle_rz_id": 0,
            "driver_id": "",
            "driver_label": "",
            "filter_pks_csv": "",
            "print_rows": print_rows,
            "file_rows": file_rows,
            "can_delete_protocol_files": _can_delete_protocol_files(request.user),
            "filter_pks": [],
            "manual_row_print_enabled": True,
            "printed_row_keys": printed_row_keys(request.user, selected_date),
            "bulk_print_config": build_bulk_print_config(
                selected_date_iso=selected_date.isoformat(),
                vehicle_rz_id=0,
                driver_id=None,
                filter_pks=[],
            ),
            **prepare_ctx,
            "print_prepare_url": reverse("waste_docs:dashboard_bulk_print_prepare"),
        },
    )


@login_required
@require_POST
def dashboard_bulk_delete_protocol(request):
    if not _can_delete_protocol_files(request.user):
        raise Http404("Stránka neexistuje.")
    selected_date = _parse_date_or_404(request.POST.get("date") or "")
    source_path = (request.POST.get("protocol_path") or "").strip()
    dashboard_bulk_url = f"{reverse('waste_docs:dashboard_bulk_print')}?date={selected_date.isoformat()}"
    if not source_path:
        messages.warning(request, "Není vybraný soubor protokolu ke smazání.")
        return redirect(dashboard_bulk_url)
    try:
        candidate = Path(source_path).resolve()
        allowed_dir = (settings.MEDIA_ROOT / "protokoly").resolve()
    except (OSError, RuntimeError, TypeError, ValueError):
        messages.warning(request, "Neplatná cesta souboru.")
        return redirect(dashboard_bulk_url)
    if allowed_dir not in candidate.parents:
        messages.warning(request, "Mazat lze pouze protokoly v adresáři media/protokoly.")
        return redirect(dashboard_bulk_url)
    if candidate.suffix.lower() not in (".pdf", ".xlsx"):
        messages.warning(request, "Mazat lze pouze PDF protokoly.")
        return redirect(dashboard_bulk_url)
    rides = rides_for_protocol_day(selected_date, request.user)
    plan_slots = plan_only_protocol_slots(selected_date)
    if not rides and not plan_slots:
        messages.warning(request, "Pro vybraný den nejsou dostupné žádné jízdy ani sloty plánu svozů.")
        return redirect(dashboard_bulk_url)
    deleted_count = delete_protocol_files_for_rides(
        rides,
        scope=PROTOCOL_SCOPE_DAY,
        selected_date=selected_date,
    )
    if deleted_count == 0:
        if not candidate.exists():
            messages.info(request, "Soubor už neexistuje.")
            return redirect(dashboard_bulk_url)
        try:
            candidate.unlink()
            deleted_count = 1
        except OSError:
            messages.error(request, "Soubor se nepodařilo smazat.")
            return redirect(dashboard_bulk_url)
    messages.success(request, f"Smazáno protokolů: {deleted_count}")
    clear_protocol_marks_for_date(selected_date)
    return redirect(dashboard_bulk_url)
