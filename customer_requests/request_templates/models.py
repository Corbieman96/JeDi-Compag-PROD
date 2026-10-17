from django.conf import settings
from django.db import models

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    NameCatalog,
    SuffixCatalog,
    VehicleKindCatalog,
    WasteTypeCatalog,
)


class CustomerRequestTemplate(models.Model):
    title = models.CharField(max_length=180, verbose_name="Název šablony")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_request_templates",
        verbose_name="Vlastník",
    )
    name = models.ForeignKey(
        NameCatalog,
        on_delete=models.PROTECT,
        related_name="customer_request_templates",
        verbose_name="Název F/P osoby",
    )
    waste_type = models.ForeignKey(
        WasteTypeCatalog,
        on_delete=models.PROTECT,
        related_name="customer_request_templates",
        verbose_name="Druh odpadu",
    )
    suffix = models.ForeignKey(
        SuffixCatalog,
        on_delete=models.PROTECT,
        related_name="customer_request_templates",
        null=True,
        blank=True,
        verbose_name="Koncovka",
    )
    address = models.ForeignKey(
        AddressCatalog,
        on_delete=models.PROTECT,
        related_name="customer_request_templates",
        verbose_name="Adresa plnění",
    )
    fulfillment_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name="Zeměpisná šířka (plnění)",
    )
    fulfillment_longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name="Zeměpisná délka (plnění)",
    )
    activity = models.ForeignKey(
        ActivityCatalog,
        on_delete=models.PROTECT,
        related_name="customer_request_templates",
        null=True,
        blank=True,
        verbose_name="Činnost",
    )
    vehicle_kind = models.ForeignKey(
        VehicleKindCatalog,
        on_delete=models.PROTECT,
        related_name="customer_request_templates",
        null=True,
        blank=True,
        verbose_name="Druh vozidla",
    )
    facility_address_snapshot = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Adresa provozovny",
    )
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name="Telefon")
    contact_note = models.CharField(max_length=200, blank=True, verbose_name="Poznámka ke kontaktu")
    contract_number = models.CharField(max_length=120, blank=True, verbose_name="Číslo smlouvy")
    note = models.CharField(max_length=200, blank=True, verbose_name="Poznámka požadavku")
    is_recurring = models.BooleanField(default=False, verbose_name="Pravidelný požadavek")
    recurrence_weekdays = models.CharField(
        max_length=40,
        blank=True,
        verbose_name="Dny v týdnu",
        help_text="CSV indexů dnů 0-6 (Po=0 ... Ne=6). Bez data požadavku a bez „Pravidelnost do“.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title", "-updated_at"]
        verbose_name = "Šablona požadavku"
        verbose_name_plural = "Šablony požadavků"

    def __str__(self):
        return self.title
