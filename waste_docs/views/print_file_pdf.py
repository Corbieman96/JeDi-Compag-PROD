from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse

from users.services.access import can_see_all_waste_docs
from waste_docs.models import Pruvodka
from waste_docs.services.reports.xlsx_to_pdf import (
    XlsxToPdfError,
    convert_xlsx_to_pdf,
    validate_print_media_rel,
)


def _user_may_print_media_rel(user, media_rel: str) -> bool:
    if can_see_all_waste_docs(user):
        return True
    rel = media_rel.replace("\\", "/").lstrip("/")
    if rel.startswith("pruvodky/"):
        return Pruvodka.objects.filter(
            generated_file=rel,
            created_by=user,
            is_archived=False,
        ).exists()
    if rel.startswith("protokoly/"):
        return Pruvodka.objects.filter(created_by=user, is_archived=False).exists()
    return False


@login_required
def print_file_as_pdf(request):
    media_rel = (request.GET.get("rel") or "").strip()
    try:
        source = validate_print_media_rel(media_rel)
    except XlsxToPdfError as exc:
        raise Http404(str(exc)) from exc
    if not _user_may_print_media_rel(request.user, media_rel):
        raise Http404("Soubor není k dispozici.")
    try:
        pdf_path = convert_xlsx_to_pdf(source, media_rel=media_rel.replace("\\", "/").lstrip("/"))
    except XlsxToPdfError as exc:
        return HttpResponse(str(exc), status=503, content_type="text/plain; charset=utf-8")
    return FileResponse(
        pdf_path.open("rb"),
        content_type="application/pdf",
        filename=pdf_path.name,
    )
