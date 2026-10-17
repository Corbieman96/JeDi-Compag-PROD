from django.db import models

from .catalogs import AddressCatalog, IcoCatalog, SuffixCatalog, WasteTypeCatalog


class SuffixSiteProfile(models.Model):
    suffix = models.OneToOneField(SuffixCatalog, on_delete=models.CASCADE, related_name="site_profile")
    name = models.CharField(max_length=255, verbose_name="Název")
    ico = models.ForeignKey(
        IcoCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suffix_site_profiles",
        verbose_name="IČO",
    )
    icz = models.CharField(max_length=50, blank=True, verbose_name="IČZ")
    facility_type = models.CharField(max_length=255, blank=True, verbose_name="Typ zařízení")
    address = models.ForeignKey(
        AddressCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suffix_site_profiles",
        verbose_name="Adresa",
    )
    zuj = models.CharField(max_length=50, blank=True, verbose_name="ZUJ")
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    accepted_waste_types = models.ManyToManyField(
        WasteTypeCatalog,
        blank=True,
        related_name="accepted_in_suffix_sites",
        verbose_name="Odpad, který přijímá",
    )
    produced_waste_types = models.ManyToManyField(
        WasteTypeCatalog,
        blank=True,
        related_name="produced_in_suffix_sites",
        verbose_name="Odpad, který vyprodukuje",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Profil koncovky"
        verbose_name_plural = "Profily koncovek"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.suffix.value})"
