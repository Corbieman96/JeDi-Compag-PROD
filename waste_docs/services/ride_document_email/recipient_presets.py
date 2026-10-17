from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from waste_docs.models import RideEmailRecipient
from waste_docs.services.ride_document_email.email_validate import normalize_recipient_email


def recipient_to_dict(row: RideEmailRecipient) -> dict:
    return {
        "id": row.pk,
        "email": row.email,
        "label": row.label or "",
        "display": row.display_label,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
    }


def list_recipients() -> list[dict]:
    rows = RideEmailRecipient.objects.all().order_by("-last_used_at", "email")
    return [recipient_to_dict(row) for row in rows]


def add_recipient(
    raw_email: str,
    *,
    label: str = "",
    user: AbstractBaseUser | None = None,
) -> tuple[RideEmailRecipient, bool]:
    email = normalize_recipient_email(raw_email)
    clean_label = (label or "").strip()[:120]
    with transaction.atomic():
        row, created = RideEmailRecipient.objects.get_or_create(
            email=email,
            defaults={
                "label": clean_label,
                "created_by": user if getattr(user, "pk", None) else None,
            },
        )
        if not created and clean_label and not row.label:
            row.label = clean_label
            row.save(update_fields=["label"])
    return row, created


def delete_recipient(pk: int) -> bool:
    deleted, _ = RideEmailRecipient.objects.filter(pk=pk).delete()
    return deleted > 0


def touch_recipient_used(raw_email: str) -> None:
    try:
        email = normalize_recipient_email(raw_email)
    except ValueError:
        return
    RideEmailRecipient.objects.filter(email=email).update(last_used_at=timezone.now())
