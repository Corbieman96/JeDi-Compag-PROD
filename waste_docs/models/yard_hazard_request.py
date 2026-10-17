from django.conf import settings
from django.db import models

from catalogs.models import (
    ActivityCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    WasteTypeCatalog,
)


class YardHazardousWasteRequest(models.Model):
    """Požadavek na nebezpečný odpad ze sběrného dvora — čeká na ruční založení jízdy."""

    class Status(models.TextChoices):
        OPEN = "open", "Otevřeno"
        RESOLVED = "resolved", "Vyřízeno"

    subject_profile = models.ForeignKey(
        NameSubjectProfile,
        on_delete=models.CASCADE,
        related_name="yard_hazard_requests",
        verbose_name="Sběrný dvůr (subjekt)",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="yard_hazard_requests_created",
    )
    waste_type = models.ForeignKey(
        WasteTypeCatalog,
        on_delete=models.PROTECT,
        related_name="yard_hazard_requests",
    )
    suffix = models.ForeignKey(
        SuffixCatalog,
        on_delete=models.PROTECT,
        related_name="yard_hazard_requests",
    )
    vehicle_kind = models.ForeignKey(
        VehicleKindCatalog,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="yard_hazard_requests",
        verbose_name="Druh vozidla",
    )
    activity = models.ForeignKey(
        ActivityCatalog,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="yard_hazard_requests",
        verbose_name="Činnost",
    )
    container_numbers = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Čísla kontejnerů",
    )
    matrix_display_label = models.CharField(max_length=200, blank=True)
    yard_contact_note = models.CharField(max_length=200, blank=True)
    source_waste_suffix_pair = models.ForeignKey(
        NameSubjectWasteSuffixPair,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="yard_hazard_requests",
    )
    submitted_date = models.DateField(
        db_index=True,
        verbose_name="Datum odeslání požadavku",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    resolved_pruvodka = models.ForeignKey(
        "Pruvodka",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="yard_hazard_request_sources",
        verbose_name="Vyřízeno průvodkou",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["submitted_date", "created_at", "pk"]
        verbose_name = "Požadavek — nebezpečný odpad ze dvora"
        verbose_name_plural = "Požadavky — nebezpečný odpad ze dvora"
        indexes = [
            models.Index(fields=["status", "submitted_date"]),
        ]

    def __str__(self) -> str:
        label = (self.matrix_display_label or "").strip()
        if label:
            return f"NO {self.submitted_date} — {label}"
        return f"NO {self.submitted_date} — {self.waste_type_id}/{self.suffix_id}"
