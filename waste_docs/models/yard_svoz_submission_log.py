"""Textový log odeslaných řádků matice sběrného dvora (pouze pro přehled na /svoz-pozadavek/)."""

from django.conf import settings
from django.db import models

from catalogs.models import (
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    WasteTypeCatalog,
)


class YardSvozSubmissionLog(models.Model):
    """Snapshot jednoho odeslaného řádku matice — nezávislý na životním cyklu SvozTask."""

    subject_profile = models.ForeignKey(
        NameSubjectProfile,
        on_delete=models.CASCADE,
        related_name="svoz_submission_logs",
        verbose_name="Sběrný dvůr (subjekt)",
    )
    submitted_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Čas odeslání")
    submission_day = models.DateField(db_index=True, verbose_name="Den odeslání")
    display_label = models.CharField(max_length=200, blank=True, verbose_name="Název řádku")
    waste_type = models.ForeignKey(
        WasteTypeCatalog,
        on_delete=models.PROTECT,
        related_name="yard_svoz_submission_logs",
    )
    suffix = models.ForeignKey(
        SuffixCatalog,
        on_delete=models.PROTECT,
        related_name="yard_svoz_submission_logs",
    )
    container_numbers = models.CharField(max_length=500, blank=True, verbose_name="Kontejner(y)")
    vehicle_kind = models.ForeignKey(
        VehicleKindCatalog,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="yard_svoz_submission_logs",
        verbose_name="Druh vozidla",
    )
    yard_contact_note = models.CharField(max_length=200, blank=True, verbose_name="Poznámka ze dvora")
    is_hazardous = models.BooleanField(default=False, verbose_name="Nebezpečný odpad")
    result_summary = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="Výsledek odeslání",
        help_text="Řidič / požadavek bez řidiče / nebezpečný odpad.",
    )
    target_date = models.DateField(null=True, blank=True, verbose_name="Cílový den na dashboardu")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="yard_svoz_submission_logs_created",
    )
    source_waste_suffix_pair = models.ForeignKey(
        NameSubjectWasteSuffixPair,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="svoz_submission_logs",
        verbose_name="Řádek matice",
    )

    class Meta:
        verbose_name = "Log odeslání matice svozu"
        verbose_name_plural = "Logy odeslání matice svozu"
        ordering = ["-submitted_at", "-pk"]
        indexes = [
            models.Index(fields=["subject_profile", "submission_day"]),
        ]

    def __str__(self) -> str:
        return f"{self.submission_day}: {self.display_label or self.waste_type_id} — {self.container_numbers}"
