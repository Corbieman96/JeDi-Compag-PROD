from django.conf import settings
from django.db import models

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    SuffixCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteTypeCatalog,
)


class RideTemplate(models.Model):
    title = models.CharField(max_length=180, verbose_name="Název šablony")
    activity = models.ForeignKey(
        ActivityCatalog,
        on_delete=models.PROTECT,
        related_name="ride_templates",
        null=True,
        blank=True,
    )
    vehicle_kind = models.ForeignKey(
        VehicleKindCatalog,
        on_delete=models.PROTECT,
        related_name="ride_templates",
        verbose_name="Druh vozidla (primární)",
    )
    applicable_vehicle_kinds = models.ManyToManyField(
        VehicleKindCatalog,
        blank=True,
        related_name="ride_templates_applicable",
        verbose_name="Platí pro druhy vozidel",
    )
    name = models.ForeignKey(NameCatalog, on_delete=models.PROTECT, related_name="ride_templates")
    ico = models.ForeignKey(IcoCatalog, on_delete=models.PROTECT, related_name="ride_templates")
    address = models.ForeignKey(AddressCatalog, on_delete=models.PROTECT, related_name="ride_templates")
    waste_type = models.ForeignKey(WasteTypeCatalog, on_delete=models.PROTECT, related_name="ride_templates")
    suffix = models.ForeignKey(
        SuffixCatalog,
        on_delete=models.PROTECT,
        related_name="ride_templates",
        null=True,
        blank=True,
    )
    vehicle_rz = models.ForeignKey(
        VehicleRzCatalog,
        on_delete=models.PROTECT,
        related_name="ride_templates",
        null=True,
        blank=True,
    )
    driver = models.ForeignKey(
        DriverProfile,
        on_delete=models.PROTECT,
        related_name="ride_templates",
        null=True,
        blank=True,
    )
    container_number = models.CharField(max_length=50, blank=True, verbose_name="Číslo kontejneru (1)")
    container_number_2 = models.CharField(max_length=50, blank=True, verbose_name="Číslo kontejneru (2)")
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name="Telefon")
    contract_number = models.CharField(max_length=120, blank=True, verbose_name="Číslo smlouvy")
    contact_note = models.CharField(max_length=200, blank=True, verbose_name="Poznámka")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ride_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title", "-updated_at"]
        verbose_name = "Šablona jízdy"
        verbose_name_plural = "Šablony jízd"

    def __str__(self):
        return self.title
