from __future__ import annotations

import os

from django.core.files.base import ContentFile
from django.db.models import Max

from customer_requests.models import CustomerRequest
from waste_docs.models import Pruvodka, PruvodkaAttachment

MAX_PRUVODKA_ATTACHMENTS = 3


def remaining_attachment_slots(pruvodka: Pruvodka) -> int:
    if not pruvodka.pk:
        return MAX_PRUVODKA_ATTACHMENTS
    return max(0, MAX_PRUVODKA_ATTACHMENTS - pruvodka.attachments.count())


def snapshot_pruvodka_form_uploads(form) -> list[tuple[str, bytes]]:
    """Read uploaded triplet once so the same files can be attached to multiple jízdy (repeat count)."""
    slots = getattr(form, "attachment_upload_slots", None) or [1, 2, 3]
    out: list[tuple[str, bytes]] = []
    for slot in slots:
        key = f"attachment_{slot}"
        f = form.cleaned_data.get(key)
        if not f:
            continue
        name = os.path.basename(getattr(f, "name", "") or "upload")
        out.append((name, f.read()))
    return out


def append_upload_snapshot_to_pruvodka(pruvodka: Pruvodka, snapshot: list[tuple[str, bytes]]) -> int:
    n = 0
    for name, data in snapshot:
        if pruvodka.attachments.count() >= MAX_PRUVODKA_ATTACHMENTS:
            break
        next_order = (
            pruvodka.attachments.aggregate(Max("sort_order"))["sort_order__max"] or 0
        ) + 1
        PruvodkaAttachment.objects.create(
            pruvodka=pruvodka,
            sort_order=next_order,
            file=ContentFile(data, name=name or f"file_{next_order}"),
        )
        n += 1
    return n


def apply_upload_snapshot_to_pruvodka(pruvodka: Pruvodka, snapshot: list[tuple[str, bytes]]) -> int:
    return append_upload_snapshot_to_pruvodka(pruvodka, snapshot)


def copy_customer_request_attachments_to_pruvodka(
    customer_request: CustomerRequest,
    pruvodka: Pruvodka,
) -> int:
    """Kopíruje soubory z požadavku do evidence jízdy (oddělené kopie v úložišti)."""
    n = 0
    for att in customer_request.attachments.all().order_by("sort_order", "id"):
        with att.file.open("rb") as src:
            data = src.read()
        name = os.path.basename(att.file.name) or f"request_{att.pk}"
        PruvodkaAttachment.objects.create(
            pruvodka=pruvodka,
            sort_order=att.sort_order,
            file=ContentFile(data, name=name),
        )
        n += 1
    return n
