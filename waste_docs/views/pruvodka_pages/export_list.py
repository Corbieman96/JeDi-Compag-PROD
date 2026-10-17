"""Stažení seznamu jízd jako XLSX (stejné filtry jako stránka seznamu)."""

from __future__ import annotations

from django.http import HttpResponse

from waste_docs.services.pruvodka_list_default_range import get_pruvodka_list_queryset_resolved
from waste_docs.services.reports.http import xlsx_attachment_response
from waste_docs.services.reports.jizdy_list_export import build_jizdy_list_xlsx_bytes
from waste_docs.views.access import waste_docs_list_access_required


@waste_docs_list_access_required
def pruvodka_list_export_xlsx(request) -> HttpResponse:
    queryset, state, _is_default_range, _show_all = get_pruvodka_list_queryset_resolved(
        request, user=request.user
    )
    payload, filename = build_jizdy_list_xlsx_bytes(queryset, state)
    return xlsx_attachment_response(payload, filename)
