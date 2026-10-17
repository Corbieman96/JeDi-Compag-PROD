"""Evidence oprav vozidla (RZ) — datum, poznámka, hodiny."""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from .catalogs import VehicleRzCatalog


class VehicleRzRepair(models.Model):
    vehicle_rz = models.ForeignKey(
        VehicleRzCatalog,
        on_delete=models.CASCADE,
        related_name="repairs",
        verbose_name="RZ vozidla",
    )
    repair_date = models.DateField(verbose_name="Datum opravy", db_index=True)
    note = models.CharField(max_length=500, blank=True, verbose_name="Poznámka")
    hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Hodiny",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_rz_repairs_created",
        verbose_name="Zadal",
    )

    class Meta:
        verbose_name = "Oprava vozidla"
        verbose_name_plural = "Opravy vozidel"
        ordering = ["-repair_date", "-pk"]
        indexes = [
            models.Index(fields=["vehicle_rz", "repair_date"]),
        ]

    def __str__(self) -> str:
        rz = self.vehicle_rz.value if self.vehicle_rz_id else "?"
        return f"{rz}: {self.repair_date} ({self.hours} h)"
