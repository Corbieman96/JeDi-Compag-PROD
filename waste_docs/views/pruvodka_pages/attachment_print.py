"""HTTP: PDF přílohy jízdy s razítkem čísla listu a data."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.http import content_disposition_header

from users.services.waste_doc_permissions import can_view_pruvodka
from waste_docs.models import Pruvodka, PruvodkaAttachment
from waste_docs.services.ride_attachment_print.stamp import stamp_attachment_pdf_bytes
from waste_docs.views.access import pruvodka_file_access_required


@pruvodka_file_access_required
def ride_attachment_print_pdf(request, pk: int, att_pk: int):
    ride = get_object_or_404(Pruvodka, pk=pk, is_archived=False)
    if not can_view_pruvodka(request.user, ride):
        raise Http404("Jízda neexistuje.")
    att = get_object_or_404(PruvodkaAttachment, pk=att_pk, pruvodka_id=ride.pk)
    if not att.file:
        raise Http404("Příloha není k dispozici.")
    name = (att.file.name or "").lower()
    if not name.endswith(".pdf"):
        raise Http404("Tisk s razítkem je jen pro PDF přílohy.")

    try:
        raw = Path(att.file.path).read_bytes()
    except (OSError, ValueError) as exc:
        raise Http404("Soubor přílohy nelze načíst.") from exc

    stamped = stamp_attachment_pdf_bytes(
        raw,
        snd_cislo_listu=ride.snd_cislo_listu or "",
        drive_date=ride.drive_date,
        ride_pk=ride.pk,
    )
    base = Path(att.filename_display or f"priloha_{att.pk}.pdf").stem
    out_name = f"{base}_tisk.pdf"
    buf = BytesIO(stamped)
    response = FileResponse(buf, content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(
        as_attachment=False,
        filename=out_name,
    )
    return response
