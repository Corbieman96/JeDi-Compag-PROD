from __future__ import annotations

import json
import re
from io import BytesIO

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST

from waste_docs.services.reports.bulk_merged_print_pdf import (
    BULK_MERGED_CACHE_SUBDIR,
    build_merged_print_pdf_bytes,
    filter_file_rows_for_print_kind,
    stream_merged_print_pdf,
)

_MERGED_PDF_NAME_RE = re.compile(r"^merged_[0-9a-f]{32}\.pdf$")
from waste_docs.services.reports.xlsx_to_pdf import XlsxToPdfError
from waste_docs.services.ride_bulk_actions import build_merged_print_file_rows
from waste_docs.views.dashboard_bulk import _parse_date_or_404


def _parse_vehicle_rz_id(raw: str) -> int:
    try:
        return max(0, int((raw or "0").strip()))
    except (ValueError, TypeError):
        return 0


def _parse_filter_pks(raw: str) -> list[int] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        pks = [int(part) for part in text.split(",") if part.strip().isdigit()]
    except ValueError:
        return None
    return pks or None


_EMPTY_PRINT_MESSAGE = "Není nic k tisku."


def _empty_print_response(*, use_stream: bool) -> HttpResponse | StreamingHttpResponse:
    if use_stream:

        def generate():
            payload = json.dumps(
                {"type": "error", "message": _EMPTY_PRINT_MESSAGE},
                ensure_ascii=False,
            )
            yield payload.encode("utf-8") + b"\n"

        return StreamingHttpResponse(generate(), content_type="application/octet-stream")
    return HttpResponse(
        _EMPTY_PRINT_MESSAGE,
        status=400,
        content_type="text/plain; charset=utf-8",
    )


def _parse_optional_driver_id(raw: str) -> int | None:
    text = (raw or "").strip()
    if not text.isdigit():
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


@login_required
@require_POST
def bulk_merged_print_pdf(request):
    selected_date = _parse_date_or_404(request.POST.get("date") or "")
    print_kind = (request.POST.get("print_kind") or "all").strip().lower()
    vehicle_rz_id = _parse_vehicle_rz_id(request.POST.get("vehicle_rz_id") or "")
    filter_pks = _parse_filter_pks(request.POST.get("pks") or "")
    driver_id = _parse_optional_driver_id(request.POST.get("driver_id") or "")
    file_rows = build_merged_print_file_rows(
        selected_date,
        request.user,
        vehicle_rz_id=vehicle_rz_id,
        filter_pks=filter_pks,
        driver_id=driver_id,
    )
    use_stream = (request.POST.get("stream") or "").strip() == "1"
    printable_rows = filter_file_rows_for_print_kind(file_rows, print_kind)
    if not printable_rows:
        return _empty_print_response(use_stream=use_stream)
    if use_stream:
        def generate():
            try:
                yield from stream_merged_print_pdf(file_rows, print_kind=print_kind)
            except XlsxToPdfError as exc:
                payload = json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False)
                yield payload.encode("utf-8") + b"\n"
            except Exception as exc:
                payload = json.dumps(
                    {"type": "error", "message": f"Sloučení PDF selhalo: {exc}"},
                    ensure_ascii=False,
                )
                yield payload.encode("utf-8") + b"\n"

        return StreamingHttpResponse(generate(), content_type="application/octet-stream")

    try:
        payload = build_merged_print_pdf_bytes(file_rows, print_kind=print_kind)
    except XlsxToPdfError as exc:
        return HttpResponse(str(exc), status=400, content_type="text/plain; charset=utf-8")
    except Exception as exc:
        return HttpResponse(
            f"Sloučení PDF selhalo: {exc}",
            status=500,
            content_type="text/plain; charset=utf-8",
        )
    rz_part = f"_rz{vehicle_rz_id}" if vehicle_rz_id > 0 else ""
    filename = f"tisk_{selected_date.isoformat()}{rz_part}_{print_kind or 'all'}.pdf"
    return FileResponse(
        BytesIO(payload),
        content_type="application/pdf",
        as_attachment=False,
        filename=filename,
    )


@login_required
def bulk_merged_print_pdf_download(request, name: str):
    """Spolehlivé stažení sloučeného PDF (funguje i při DEBUG=False, kdy se /media neservíruje)."""
    if not _MERGED_PDF_NAME_RE.match(name or ""):
        raise Http404("Neplatný název souboru.")
    cache_dir = (settings.MEDIA_ROOT / "print_cache" / BULK_MERGED_CACHE_SUBDIR).resolve()
    target = (cache_dir / name).resolve()
    if cache_dir not in target.parents or not target.is_file():
        raise Http404("Sloučené PDF není k dispozici.")
    return FileResponse(
        target.open("rb"),
        content_type="application/pdf",
        as_attachment=False,
        filename=name,
    )
