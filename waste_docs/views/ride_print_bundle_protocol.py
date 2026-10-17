"""Generování a mazání protokolu jízdy (jizda.xlsx) na stránce tisku skupiny RZ."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from waste_docs.services.ride_bulk_actions import (
    append_protocol_and_supplement_file_rows,
    delete_protocol_files_for_rides,
)
from waste_docs.services.ride_print_bundle_urls import ride_print_bundle_url
from waste_docs.services.ride_protocol_xlsx import PROTOCOL_SCOPE_GROUP, rides_for_protocol_group
from waste_docs.views.dashboard_bulk import _can_delete_protocol_files, _parse_date_or_404


def _parse_vehicle_rz_id_or_404(raw: str) -> int:
    try:
        vehicle_rz_id = int((raw or "").strip())
    except (TypeError, ValueError) as exc:
        raise Http404("Neplatné vozidlo.") from exc
    if vehicle_rz_id <= 0:
        raise Http404("Neplatné vozidlo.")
    return vehicle_rz_id


def _parse_filter_pks(raw: str) -> list[int]:
    pks_raw = (raw or "").strip()
    if not pks_raw:
        return []
    try:
        return [int(p) for p in pks_raw.split(",") if p.strip().isdigit()]
    except ValueError:
        return []


def _parse_optional_driver_id(raw: str) -> int | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


@login_required
@require_POST
def ride_print_bundle_generate_protocol(request):
    selected_date = _parse_date_or_404(request.POST.get("date") or "")
    vehicle_rz_id = _parse_vehicle_rz_id_or_404(request.POST.get("vehicle_rz_id") or "")
    filter_pks = _parse_filter_pks(request.POST.get("pks") or "")
    driver_id = _parse_optional_driver_id(request.POST.get("driver_id") or "")
    return_url = (request.POST.get("next") or "").strip() or ride_print_bundle_url(
        selected_date=selected_date,
        vehicle_rz_id=vehicle_rz_id,
        filter_pks=filter_pks,
        driver_id=driver_id,
    )

    rides = rides_for_protocol_group(
        selected_date,
        vehicle_rz_id,
        request.user,
        filter_pks=filter_pks or None,
        driver_id=driver_id,
    )
    if not rides:
        messages.warning(request, "Pro vybranou skupinu nejsou dostupné žádné jízdy.")
        return redirect(return_url)

    file_rows = append_protocol_and_supplement_file_rows(
        [],
        rides,
        selected_date,
        scope=PROTOCOL_SCOPE_GROUP,
        force_regenerate=True,
    )
    if any(row.get("kind") == "protocol" for row in file_rows):
        messages.success(request, "PDF protokol jízd byl vygenerován.")
    else:
        messages.warning(request, "Protokol se nepodařilo vygenerovat.")
    return redirect(return_url)


@login_required
@require_POST
def ride_print_bundle_delete_protocol(request):
    if not _can_delete_protocol_files(request.user):
        raise Http404("Stránka neexistuje.")

    selected_date = _parse_date_or_404(request.POST.get("date") or "")
    vehicle_rz_id = _parse_vehicle_rz_id_or_404(request.POST.get("vehicle_rz_id") or "")
    filter_pks = _parse_filter_pks(request.POST.get("pks") or "")
    driver_id = _parse_optional_driver_id(request.POST.get("driver_id") or "")
    source_path = (request.POST.get("protocol_path") or "").strip()
    return_url = (request.POST.get("next") or "").strip() or ride_print_bundle_url(
        selected_date=selected_date,
        vehicle_rz_id=vehicle_rz_id,
        filter_pks=filter_pks,
        driver_id=driver_id,
    )

    if not source_path:
        messages.warning(request, "Není vybraný soubor protokolu ke smazání.")
        return redirect(return_url)
    try:
        candidate = Path(source_path).resolve()
        allowed_dir = (settings.MEDIA_ROOT / "protokoly").resolve()
    except (OSError, RuntimeError, TypeError, ValueError):
        messages.warning(request, "Neplatná cesta souboru.")
        return redirect(return_url)
    if allowed_dir not in candidate.parents:
        messages.warning(request, "Mazat lze pouze protokoly v adresáři media/protokoly.")
        return redirect(return_url)
    if candidate.suffix.lower() not in (".pdf", ".xlsx"):
        messages.warning(request, "Mazat lze pouze PDF protokoly.")
        return redirect(return_url)

    rides = rides_for_protocol_group(
        selected_date,
        vehicle_rz_id,
        request.user,
        filter_pks=filter_pks or None,
        driver_id=driver_id,
    )
    if not rides:
        messages.warning(request, "Pro vybranou skupinu nejsou dostupné žádné jízdy.")
        return redirect(return_url)

    deleted_count = 0
    if candidate.is_file():
        try:
            candidate.unlink()
            deleted_count = 1
        except OSError:
            messages.error(request, "Soubor se nepodařilo smazat.")
            return redirect(return_url)
    deleted_count += delete_protocol_files_for_rides(
        rides,
        scope=PROTOCOL_SCOPE_GROUP,
        selected_date=selected_date,
    )
    if deleted_count == 0:
        messages.info(request, "Protokol už neexistuje.")
        return redirect(return_url)
    messages.success(request, f"Smazáno protokolů: {deleted_count}")
    return redirect(return_url)
