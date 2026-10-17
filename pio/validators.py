from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError


def pio_max_upload_bytes() -> int:
    return int(getattr(settings, "PIO_MAX_UPLOAD_BYTES", 10 * 1024 * 1024))


def validate_pio_upload_size(uploaded_file) -> None:
    """Odmítne příliš velké soubory (PDF/obrázky u revizí PIO)."""
    max_b = pio_max_upload_bytes()
    size = getattr(uploaded_file, "size", None)
    if size is None:
        return
    if size > max_b:
        mb = max_b / (1024 * 1024)
        raise ValidationError(
            f"Soubor je příliš velký. Maximální velikost je {mb:.1f} MiB.",
            code="pio_file_too_large",
        )
