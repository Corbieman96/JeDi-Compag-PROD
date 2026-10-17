from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

from pio.validators import validate_pio_upload_size


def _pio_upload_to(instance: "PioRevision", filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in (".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".xls"):
        ext = Path(filename).suffix or ".pdf"
    return f"pio/revisions/pair_{instance.pair_id}/{uuid.uuid4().hex}{ext}"


class PioRevision(models.Model):
    """Jedna nahraná verze PIO k řádku pár odpad–koncovka u subjektu."""

    pair = models.ForeignKey(
        "catalogs.NameSubjectWasteSuffixPair",
        on_delete=models.CASCADE,
        related_name="pio_revisions",
        verbose_name="Pár odpad–koncovka",
    )
    file = models.FileField(
        upload_to=_pio_upload_to,
        verbose_name="Soubor",
        validators=[
            validate_pio_upload_size,
            FileExtensionValidator(["pdf", "png", "jpg", "jpeg", "xlsx", "xls"]),
        ],
    )
    note = models.CharField(max_length=255, blank=True, verbose_name="Poznámka")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Nahráno")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pio_revisions_created",
        verbose_name="Nahrál",
    )

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "Revize PIO"
        verbose_name_plural = "Revize PIO"

    def __str__(self):
        return f"PIO revize #{self.pk} (pár {self.pair_id})"
