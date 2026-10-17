"""Kontext tisknutelných PDF příloh jízdy pro detail."""

from __future__ import annotations

from django.urls import reverse

from waste_docs.models import Pruvodka, PruvodkaAttachment


def _is_pdf_attachment(att: PruvodkaAttachment) -> bool:
    name = (att.file.name or "").lower()
    return name.endswith(".pdf")


def attachment_print_items_for_ride(ride: Pruvodka) -> list[dict]:
    """
    Položky pro JS na detailu: label + URL stamped print.pdf.
    Jen PDF přílohy této jízdy.
    """
    items: list[dict] = []
    for att in ride.attachments.all():
        if not att.file or not _is_pdf_attachment(att):
            continue
        items.append(
            {
                "id": att.pk,
                "label": att.filename_display or f"Příloha #{att.pk}",
                "printUrl": reverse(
                    "waste_docs:ride_attachment_print_pdf",
                    kwargs={"pk": ride.pk, "att_pk": att.pk},
                ),
            }
        )
    return items
