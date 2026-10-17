"""Satelitní 1:1 profily k NameSubjectProfile — oddělení domén pro údržbu."""

from __future__ import annotations

from django.db import models

from .catalogs import AddressCatalog, SuffixCatalog, WasteTypeCatalog


class SubjectContactProfile(models.Model):
    subject = models.OneToOneField(
        "catalogs.NameSubjectProfile",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="contact_profile",
        verbose_name="Subjekt",
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Telefon",
        help_text="Ve tvaru 000 000 000",
    )
    contact_note = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Poznámka",
    )

    class Meta:
        verbose_name = "Kontakt subjektu"
        verbose_name_plural = "Kontakty subjektů"


class SubjectAddressProfile(models.Model):
    subject = models.OneToOneField(
        "catalogs.NameSubjectProfile",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="address_profile",
        verbose_name="Subjekt",
    )
    facility_address = models.ForeignKey(
        AddressCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="facility_subject_address_profiles",
        verbose_name="Adresa provozovny",
    )
    fulfillment_address = models.ForeignKey(
        AddressCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fulfillment_subject_address_profiles",
        verbose_name="Adresa plnění",
    )
    facility_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    facility_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    fulfillment_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    fulfillment_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    fulfillment_orp = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="ORP Adresa plnění (Obec s rozšířenou působností)",
    )
    fulfillment_iczuj = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="IČZÚJ (identifikační číslo základní územní jednotky)",
    )

    class Meta:
        verbose_name = "Adresa a geodata subjektu"
        verbose_name_plural = "Adresy a geodata subjektů"


class SubjectYardSettings(models.Model):
    subject = models.OneToOneField(
        "catalogs.NameSubjectProfile",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="yard_settings",
        verbose_name="Subjekt",
    )
    is_collection_yard = models.BooleanField(
        default=False,
        verbose_name="Lokalita sběrného dvora",
        help_text="Zapněte u subjektů, kde se zadávají požadavky na svoz z matice a případně průvodky z dvora.",
    )
    yard_allow_pruvodka = models.BooleanField(
        default=False,
        verbose_name="Povolit průvodku z dvora",
        help_text="Globálně povolí cestu „Nová jízda“ pro tento subjekt sběrného dvora.",
    )
    yard_allow_matrix = models.BooleanField(
        default=False,
        verbose_name="Povolit matici požadavků",
        help_text="Globálně povolí cestu „Požadavek na svoz“ (matice) pro tento subjekt sběrného dvora.",
    )
    yard_svoz_dispatch_group = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Skupina v plánu svozů",
        help_text="Volitelný název pro přehled u dispečera (např. Sever, Bakov). Nepřiřazuje řidiče — jen seskupení na obrazovce plánu.",
    )
    yard_svoz_ratio_min_containers = models.PositiveSmallIntegerField(
        default=5,
        verbose_name="Min. požadavků pro poměr řidičů",
        help_text=(
            "Při menším počtu otevřených požadavků běžného svozu na daný den se úkoly "
            "přiřadí jen prvnímu řidiči (B1). Každý sběrný dvůr může mít jinou hodnotu."
        ),
    )

    class Meta:
        verbose_name = "Nastavení sběrného dvora"
        verbose_name_plural = "Nastavení sběrných dvorů"


class SubjectZpoSettings(models.Model):
    subject = models.OneToOneField(
        "catalogs.NameSubjectProfile",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="zpo_settings",
        verbose_name="Subjekt",
    )
    system_generates_zpo = models.BooleanField(
        default=True,
        verbose_name="Generovat systémové ZPO k jízdám",
        help_text="Vypněte, pokud ZPO/podklady k jízdám dostáváte mimo systém nebo systémové ZPO u tohoto subjektu nepotřebujete.",
    )

    class Meta:
        verbose_name = "Globální ZPO u subjektu"
        verbose_name_plural = "Globální ZPO u subjektů"


class SubjectPioProfile(models.Model):
    subject = models.OneToOneField(
        "catalogs.NameSubjectProfile",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="pio_profile",
        verbose_name="Subjekt",
    )
    pio_officer_name = models.CharField(max_length=255, blank=True, verbose_name="PIO — jméno odpovědné osoby")
    pio_officer_phone = models.CharField(max_length=20, blank=True, verbose_name="PIO — telefon osoby")
    pio_officer_email = models.EmailField(blank=True, verbose_name="PIO — e-mail")
    pio_waste_type = models.ForeignKey(
        WasteTypeCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pio_subject_profiles",
        verbose_name="PIO — vybraný druh odpadu",
    )
    pio_suffix = models.ForeignKey(
        SuffixCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pio_subject_profiles",
        verbose_name="PIO — vybraná koncovka",
    )
    pio_outside_map_lat = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name="PIO — mimo provozovnu (lat)",
    )
    pio_outside_map_lng = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name="PIO — mimo provozovnu (lng)",
    )
    pio_outside_map_orp = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="PIO — ORP z mapy (placeholder iczujfirmy)",
    )
    pio_outside_map_iczuj = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="PIO — IČZÚJ z mapy (placeholder orp)",
    )

    class Meta:
        verbose_name = "PIO profil subjektu"
        verbose_name_plural = "PIO profily subjektů"
