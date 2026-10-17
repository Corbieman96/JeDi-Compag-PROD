"""Archivace aktivního PIO z pole na páru do revizí (bez trvalého smazání)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from django.core.files.base import ContentFile

from pio.models import PioRevision

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

    from catalogs.models import NameSubjectWasteSuffixPair


def archive_pair_pio_document(
    pair: NameSubjectWasteSuffixPair,
    *,
    note: str = "",
    created_by: AbstractBaseUser | None = None,
) -> PioRevision | None:
    """
    Zkopíruje ``pair.pio_document`` do archivu revizí a vyprázdní aktivní pole na páru.
  """
    if not pair.pk:
        return None
    field = pair.pio_document
    if not field or not getattr(field, "name", ""):
        return None

    name = os.path.basename(field.name)
    with field.open("rb") as fh:
        content = fh.read()

    rev = PioRevision(
        pair=pair,
        note=note or "Přesunuto z aktivního PIO u páru",
        created_by=created_by if created_by and created_by.is_authenticated else None,
    )
    rev.file.save(name, ContentFile(content), save=True)

    field.delete(save=False)
    pair.pio_document = None
    pair.save(update_fields=["pio_document"])
    return rev


def set_pair_active_pio_from_revision(pair: NameSubjectWasteSuffixPair, rev: PioRevision) -> None:
    """Nastaví aktivní ``pio_document`` na páru jako kopii nahrané revize (pro tisk u jízdy)."""
    if not rev.file or not getattr(rev.file, "name", ""):
        return
    name = os.path.basename(rev.file.name)
    with rev.file.open("rb") as fh:
        content = fh.read()
    pair.pio_document.save(name, ContentFile(content), save=True)
