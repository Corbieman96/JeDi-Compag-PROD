"""Sloučený PDF tisk bianko průvodek."""

from __future__ import annotations

import json
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST

from waste_docs.services.blank_pruvodka.print_bundle import (
    build_blank_print_file_rows,
    parse_blank_print_pks,
)
from waste_docs.services.reports.bulk_merged_print_pdf import (
    build_merged_print_pdf_bytes,
    filter_file_rows_for_print_kind,
    stream_merged_print_pdf,
)
from waste_docs.services.reports.xlsx_to_pdf import XlsxToPdfError


@login_required
@require_POST
def blank_pruvodka_merged_print_pdf(request):
    pks = parse_blank_print_pks(
        pks_raw=request.POST.get("pks") or "",
        pk_raw=request.POST.get("pk") or "",
    )
    if not pks:
        raise Http404("Chybí parametr pks.")

    print_kind = (request.POST.get("print_kind") or "xlsx").strip().lower()
    use_stream = (request.POST.get("stream") or "").strip() == "1"

    _, file_rows, _ = build_blank_print_file_rows(pks, request.user)
    if not filter_file_rows_for_print_kind(file_rows, print_kind):
        msg = "Není nic k tisku."
        if use_stream:

            def generate_empty():
                payload = json.dumps({"type": "error", "message": msg}, ensure_ascii=False)
                yield payload.encode("utf-8") + b"\n"

            return StreamingHttpResponse(generate_empty(), content_type="application/octet-stream")
        return HttpResponse(msg, status=400, content_type="text/plain; charset=utf-8")
    if use_stream:

        def generate():
            try:
                yield from stream_merged_print_pdf(file_rows, print_kind=print_kind)
            except XlsxToPdfError as exc:
                payload = json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False)
                yield payload.encode("utf-8") + b"\n"

        return StreamingHttpResponse(generate(), content_type="application/octet-stream")

    try:
        payload = build_merged_print_pdf_bytes(file_rows, print_kind=print_kind)
    except XlsxToPdfError as exc:
        return HttpResponse(str(exc), status=400, content_type="text/plain; charset=utf-8")

    filename = f"bianko_tisk_{len(pks)}_ks_{print_kind or 'xlsx'}.pdf"
    return FileResponse(
        BytesIO(payload),
        content_type="application/pdf",
        as_attachment=False,
        filename=filename,
    )
