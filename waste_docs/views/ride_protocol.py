from __future__ import annotations

from datetime import date

from django.http import FileResponse, Http404
from django.contrib.auth.decorators import login_required

from waste_docs.services.ride_bulk_actions import _ensure_protocol_pdf
from waste_docs.services.ride_protocol_xlsx import (
    PROTOCOL_SCOPE_DAY,
    PROTOCOL_SCOPE_GROUP,
    PROTOCOL_SCOPE_SINGLE,
    generate_protocol_xlsx,
    rides_for_protocol_day,
    rides_for_protocol_group,
    rides_for_protocol_single,
)


def _parse_group_params_or_404(date_raw: str, vehicle_raw: str) -> tuple[date, int]:
    try:
        selected_date = date.fromisoformat((date_raw or "").strip())
        vehicle_rz_id = int((vehicle_raw or "").strip())
    except (TypeError, ValueError) as exc:
        raise Http404("Neplatné parametry protokolu.") from exc
    return selected_date, vehicle_rz_id


def _parse_optional_driver_id(raw: str) -> int | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _parse_optional_pks(raw: str) -> list[int] | None:
    text = (raw or "").strip()
    if not text:
        return None
    out: list[int] = []
    for chunk in text.split(","):
        part = chunk.strip()
        if part.isdigit():
            out.append(int(part))
    return out or None


def _protocol_pdf_response(
    rides: list,
    *,
    scope: str,
    selected_date: date | None = None,
) -> FileResponse:
    if not rides:
        raise Http404("Protokol není k dispozici.")
    output_path = generate_protocol_xlsx(rides, scope=scope, selected_date=selected_date)
    pdf_path = _ensure_protocol_pdf(output_path)
    return FileResponse(
        pdf_path.open("rb"),
        content_type="application/pdf",
        filename=pdf_path.name,
    )


@login_required
def ride_protocol_group_xlsx(request):
    selected_date, vehicle_rz_id = _parse_group_params_or_404(
        request.GET.get("date"),
        request.GET.get("vehicle_rz_id"),
    )
    filter_pks = _parse_optional_pks(request.GET.get("pks") or "")
    driver_id = _parse_optional_driver_id(request.GET.get("driver_id") or "")
    rides = rides_for_protocol_group(
        selected_date,
        vehicle_rz_id,
        request.user,
        filter_pks=filter_pks,
        driver_id=driver_id,
    )
    if not rides:
        raise Http404("Pro vybranou skupinu nejsou dostupné žádné jízdy.")
    output_path = generate_protocol_xlsx(rides, scope=PROTOCOL_SCOPE_GROUP)
    return FileResponse(
        output_path.open("rb"),
        as_attachment=True,
        filename=output_path.name,
    )


@login_required
def ride_protocol_group_pdf(request):
    selected_date, vehicle_rz_id = _parse_group_params_or_404(
        request.GET.get("date"),
        request.GET.get("vehicle_rz_id"),
    )
    filter_pks = _parse_optional_pks(request.GET.get("pks") or "")
    driver_id = _parse_optional_driver_id(request.GET.get("driver_id") or "")
    rides = rides_for_protocol_group(
        selected_date,
        vehicle_rz_id,
        request.user,
        filter_pks=filter_pks,
        driver_id=driver_id,
    )
    return _protocol_pdf_response(rides, scope=PROTOCOL_SCOPE_GROUP, selected_date=selected_date)


@login_required
def ride_protocol_day_xlsx(request):
    try:
        selected_date = date.fromisoformat((request.GET.get("date") or "").strip())
    except ValueError as exc:
        raise Http404("Neplatné datum.") from exc
    rides = rides_for_protocol_day(selected_date, request.user)
    if not rides:
        raise Http404("Pro vybraný den nejsou dostupné žádné jízdy.")
    output_path = generate_protocol_xlsx(
        rides,
        scope=PROTOCOL_SCOPE_DAY,
        selected_date=selected_date,
    )
    return FileResponse(
        output_path.open("rb"),
        as_attachment=True,
        filename=output_path.name,
    )


@login_required
def ride_protocol_single_xlsx(request, pk: int):
    rides = rides_for_protocol_single(pk, request.user)
    if not rides:
        raise Http404("Jízda neexistuje.")
    output_path = generate_protocol_xlsx(rides, scope=PROTOCOL_SCOPE_SINGLE)
    return FileResponse(
        output_path.open("rb"),
        as_attachment=True,
        filename=output_path.name,
    )


@login_required
def ride_protocol_single_pdf(request, pk: int):
    rides = rides_for_protocol_single(pk, request.user)
    return _protocol_pdf_response(rides, scope=PROTOCOL_SCOPE_SINGLE)
