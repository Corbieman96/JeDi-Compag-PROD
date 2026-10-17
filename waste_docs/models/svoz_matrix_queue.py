"""Fronta řádků matice sběrného dvora — odložené zpracování (okno 11–13, process po 17:00)."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair


class SvozMatrixQueueEntry(models.Model):
    """Jeden řádek matice čekající na zpracování po process_after."""

    class Status(models.TextChoices):
        PENDING = "pending", "Čeká"
        PROCESSED = "processed", "Zpracováno"
        SKIPPED_DUPLICATE = "skipped_duplicate", "Duplicita (přeskočeno)"
        FAILED = "failed", "Chyba"

    subject_profile = models.ForeignKey(
        NameSubjectProfile,
        on_delete=models.CASCADE,
        related_name="svoz_matrix_queue_entries",
        verbose_name="Sběrný dvůr",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="svoz_matrix_queue_entries",
    )
    source_waste_suffix_pair = models.ForeignKey(
        NameSubjectWasteSuffixPair,
        on_delete=models.PROTECT,
        related_name="svoz_matrix_queue_entries",
        verbose_name="Řádek matice",
    )
    container_numbers = models.CharField(max_length=500, verbose_name="Čísla kontejnerů")
    matrix_display_label = models.CharField(max_length=200, blank=True)
    yard_contact_note = models.CharField(max_length=200, blank=True)
    target_date = models.DateField(db_index=True, verbose_name="Cílový den (zmrazeno při odeslání)")
    submitted_at = models.DateTimeField(default=timezone.now, db_index=True)
    process_after = models.DateTimeField(db_index=True, verbose_name="Zpracovat nejdříve od")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    result_svoz_task = models.ForeignKey(
        "waste_docs.SvozTask",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="svoz_matrix_queue_sources",
        verbose_name="Vzniklý požadavek",
    )
    attempt_count = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ["submitted_at", "pk"]
        verbose_name = "Fronta matice svozu (SD)"
        verbose_name_plural = "Fronta matice svozu (SD)"
        indexes = [
            models.Index(fields=["status", "process_after"]),
        ]

    def __str__(self):
        return f"Queue {self.pk} {self.target_date} — {self.status}"
