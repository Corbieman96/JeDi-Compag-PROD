"""Pasport kontejneru — evidence podle druhu vozidla (VehicleKindCatalog)."""

from __future__ import annotations

import uuid
from pathlib import Path

from django.db import models

from catalogs.models.pasport_stredisko import PasportStredisko
from catalogs.models.vehicle_rz import VehicleKindCatalog


def _container_photo_upload_to(instance: "ContainerPassport", filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    folder = instance.pk if instance.pk else uuid.uuid4().hex[:12]
    return f"container_passports/{folder}/{uuid.uuid4().hex[:10]}{ext}"


class ContainerPassport(models.Model):
    class ContainerSizeFt(models.IntegerChoices):
        FT20 = 20, "20′"
        FT40 = 40, "40′"

    container_number = models.CharField(
        max_length=80,
        unique=True,
        verbose_name="Číslo kontejneru",
    )
    vehicle_kind = models.ForeignKey(
        VehicleKindCatalog,
        on_delete=models.PROTECT,
        related_name="container_passports",
        verbose_name="Druh vozidla",
        help_text="Stejný číselník jako /catalogs/vehicle-rz/kinds/",
    )
    stredisko = models.ForeignKey(
        PasportStredisko,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="container_passports",
        verbose_name="Středisko",
    )
    container_size_ft = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=ContainerSizeFt.choices,
        verbose_name="Velikost (′)",
        help_text="Volitelně 20′ nebo 40′ (ručně); z VOK se bere spíš objem m³.",
    )
    volume_m3 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Objem (m³)",
        help_text="Objem kontejneru v m³ (např. z VOK / sloupec m³).",
    )
    vehicle_requirement_note = models.CharField(
        max_length=40,
        blank=True,
        verbose_name="Požadavek na vozidlo",
        help_text="Např. 3H u většího objemu (≥ 30 m³) nebo u 40′ — z importu VOK nebo ručně.",
    )
    color = models.CharField(max_length=120, verbose_name="Barva")
    year_manufactured = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Rok výroby",
    )
    photo_1 = models.ImageField(
        upload_to=_container_photo_upload_to,
        verbose_name="Fotografie 1",
        blank=True,
        null=True,
    )
    photo_2 = models.ImageField(
        upload_to=_container_photo_upload_to,
        verbose_name="Fotografie 2",
        blank=True,
        null=True,
    )
    photo_3 = models.ImageField(
        upload_to=_container_photo_upload_to,
        verbose_name="Fotografie 3",
        blank=True,
        null=True,
    )
    notes = models.TextField(blank=True, verbose_name="Poznámka")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pasport kontejneru"
        verbose_name_plural = "Pasy kontejnerů"
        ordering = ["vehicle_kind__sort_order", "vehicle_kind__name", "container_number"]

    def __str__(self) -> str:
        return f"{self.container_number} — {self.vehicle_kind}"
