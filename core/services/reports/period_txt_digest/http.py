"""HTTP odpověď pro TXT výcuc."""

from __future__ import annotations

from django.http import HttpResponse
from django.utils.http import content_disposition_header


def txt_attachment_response(*, filename: str, content: bytes) -> HttpResponse:
    safe_name = (filename or "vyucuc.txt").replace('"', "")
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = content_disposition_header(
        as_attachment=True,
        filename=safe_name,
    )
    return response
