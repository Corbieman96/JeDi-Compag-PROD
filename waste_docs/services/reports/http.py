"""HTTP odpovědi pro stažení tabulkových exportů."""

from __future__ import annotations

from django.http import HttpResponse
from django.utils.http import content_disposition_header


def xlsx_attachment_response(data: bytes, filename: str) -> HttpResponse:
    resp = HttpResponse(
        data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=filename)
    return resp
