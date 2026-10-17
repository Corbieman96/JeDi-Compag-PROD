from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from catalogs.waste_catalog_code import normalize_waste_catalog_code


class NameCatalog(models.Model):
    value = models.CharField(max_length=255, unique=True, verbose_name="Název F/P osoby")

    class Meta:
        verbose_name = "Název F/P osoby"
        verbose_name_plural = "Názvy F/P osob"
        ordering = ["value"]

    def __str__(self):
        return self.value


class IcoCatalog(models.Model):
    value = models.CharField(max_length=8, unique=True, verbose_name="IČO")

    class Meta:
        verbose_name = "IČO"
        verbose_name_plural = "IČO"
        ordering = ["value"]

    def __str__(self):
        return self.value


class AddressCatalog(models.Model):
    value = models.CharField(max_length=255, unique=True, verbose_name="Adresa")

    class Meta:
        verbose_name = "Adresa"
        verbose_name_plural = "Adresy"
        ordering = ["value"]

    def __str__(self):
        return self.value


class WasteTypeCatalog(models.Model):
    code = models.CharField(max_length=30, unique=True, verbose_name="Kód odpadu")
    value = models.CharField(max_length=255, verbose_name="Název druhu odpadu")
    category = models.CharField(max_length=20, blank=True, verbose_name="Kategorie")
    description_fo = models.TextField(blank=True, verbose_name="Popis odpadu pro FO")
    description_po = models.TextField(blank=True, verbose_name="Popis odpadu pro PO")

    class Meta:
        verbose_name = "Druh odpadu"
        verbose_name_plural = "Druhy odpadu"
        ordering = ["code", "value"]

    def __str__(self):
        code_disp = normalize_waste_catalog_code(self.code)
        if code_disp:
            return code_disp
        return self.value


class WasteCodeCatalog(models.Model):
    value = models.CharField(max_length=20, unique=True, verbose_name="Katalogové číslo odpadu")

    class Meta:
        verbose_name = "Katalogové číslo odpadu"
        verbose_name_plural = "Katalogová čísla odpadu"
        ordering = ["value"]

    def __str__(self):
        return self.value


class WasteCategoryCatalog(models.Model):
    value = models.CharField(max_length=20, unique=True, verbose_name="Kategorie odpadu")

    class Meta:
        verbose_name = "Kategorie odpadu"
        verbose_name_plural = "Kategorie odpadu"
        ordering = ["value"]

    def __str__(self):
        return self.value


class VehicleRzCatalog(models.Model):
    value = models.CharField(max_length=20, unique=True, verbose_name="RZ vozidla")

    class Meta:
        verbose_name = "RZ vozidla"
        verbose_name_plural = "RZ vozidel"
        ordering = ["value"]

    def __str__(self):
        return self.value

    def svoz_plan_option_label(self) -> str:
        """Text do comboboxu plánu svozů: RZ + typ z profilu (pokud existuje a je vyplněn)."""
        try:
            pt = (self.profile.vehicle_type or "").strip()
        except ObjectDoesNotExist:
            return self.value
        return f"{self.value} — {pt}" if pt else self.value


class SuffixCatalog(models.Model):
    value = models.CharField(max_length=255, unique=True, verbose_name="Koncovka")

    class Meta:
        verbose_name = "Koncovka"
        verbose_name_plural = "Koncovky"
        ordering = ["value"]

    def __str__(self):
        return self.value
