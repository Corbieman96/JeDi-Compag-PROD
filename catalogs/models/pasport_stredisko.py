"""Středisko pro pasport kontejneru (B110, B120, …)."""

from __future__ import annotations

from django.db import models


class PasportStredisko(models.Model):
    code = models.CharField(max_length=32, unique=True, verbose_name="Kód střediska")
    name = models.CharField(max_length=200, blank=True, verbose_name="Název")
    sort_order = models.PositiveIntegerField(default=0, db_index=True, verbose_name="Pořadí")
    is_active = models.BooleanField(default=True, verbose_name="Aktivní")

    class Meta:
        verbose_name = "Středisko pasportů"
        verbose_name_plural = "Střediska pasportů"
        ordering = ["sort_order", "code", "pk"]

    def __str__(self) -> str:
        if self.name:
            return f"{self.code} — {self.name}"
        return self.code
