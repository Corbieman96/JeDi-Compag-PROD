from django.db import models

from .catalogs import SuffixCatalog, WasteTypeCatalog


class ZpoDocument(models.Model):
    """Centralni knihovna souboru ZPO — sdilena mezi vsemi subjekty."""

    label = models.CharField(max_length=200, verbose_name="Popisek")
    file = models.FileField(upload_to="zpo_library/", verbose_name="Soubor ZPO")
    waste_type = models.ForeignKey(
        WasteTypeCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="zpo_documents",
        verbose_name="Druh odpadu",
    )
    suffix = models.ForeignKey(
        SuffixCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="zpo_documents",
        verbose_name="Koncovka",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ZPO v knihovně"
        verbose_name_plural = "Knihovna ZPO"
        ordering = ["label", "id"]

    def __str__(self):
        return self.label or f"ZPO #{self.pk}"
