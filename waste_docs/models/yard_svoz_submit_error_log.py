"""Chybový log odeslání matice — jeden záznam patří jednomu sběrnému dvoru."""

from django.conf import settings
from django.db import models

from catalogs.models import NameSubjectProfile


class YardSvozSubmitErrorLog(models.Model):
    """Jedna chyba (nebo tiché přeskočení) při POST /svoz-pozadavek/ u konkrétního dvora."""

    class Source(models.TextChoices):
        SUBMIT = "submit", "Odeslání"
        LIVE = "live", "Živá kontrola"
        LOGIN = "login", "Přihlášení"
        OPEN = "open", "Otevření matice"
        SESSION = "session", "Relace"

    subject_profile = models.ForeignKey(
        NameSubjectProfile,
        on_delete=models.CASCADE,
        related_name="svoz_submit_error_logs",
        verbose_name="Sběrný dvůr (subjekt)",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Čas")
    submission_day = models.DateField(db_index=True, verbose_name="Den")
    message = models.TextField(verbose_name="Text chyby")
    source = models.CharField(
        max_length=16,
        choices=Source.choices,
        default=Source.SUBMIT,
        db_index=True,
        verbose_name="Zdroj",
    )
    display_label = models.CharField(max_length=200, blank=True, verbose_name="Řádek matice")
    container_numbers = models.CharField(max_length=500, blank=True, verbose_name="Kontejner(y)")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="yard_svoz_submit_error_logs_created",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True, verbose_name="Přečteno")
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="yard_svoz_submit_error_logs_acked",
    )

    class Meta:
        verbose_name = "Chyba odeslání matice svozu"
        verbose_name_plural = "Chyby odeslání matice svozu"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["subject_profile", "-created_at"]),
            models.Index(fields=["acknowledged_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.submission_day}: {self.message[:80]}"
