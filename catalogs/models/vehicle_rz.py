from django.db import models

from .catalogs import VehicleRzCatalog


class VehicleKindCatalog(models.Model):
    name = models.CharField(max_length=120, unique=True, verbose_name="Název druhu")
    shortcut = models.CharField(max_length=20, unique=True, verbose_name="Zkratka")
    sort_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
        verbose_name="Pořadí",
        help_text="Nižší číslo = dříve v seznamech a ve sloupcích na dashboardu.",
    )
    parent_kind = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_kinds",
        verbose_name="Nadřazený druh",
        help_text="Např. 3H pod H, nebo H pod A. Potomci a předci se použijí při párování plánu, RZ a pasportů.",
    )
    extra_compatible_kinds = models.ManyToManyField(
        "self",
        symmetrical=True,
        blank=True,
        verbose_name="Další kompatibilní druhy",
        help_text="Ruční vazby mimo strom (obousměrně).",
    )

    class Meta:
        verbose_name = "Druh vozidla"
        verbose_name_plural = "Druhy vozidel"
        ordering = ["sort_order", "name"]

    def display_label(self) -> str:
        """Lidsky čitelný popisek: Název (zkratka), např. Hák (H)."""
        name = (self.name or "").strip()
        sc = (self.shortcut or "").strip()
        if name and sc:
            return f"{name} ({sc})"
        return name or sc or "?"

    def __str__(self) -> str:
        return self.display_label()


class VehicleRzProfile(models.Model):
    rz = models.OneToOneField(VehicleRzCatalog, on_delete=models.CASCADE, related_name="profile")
    vehicle_type = models.CharField(max_length=120, blank=True, verbose_name="Typ vozidla")
    has_trailer = models.BooleanField(default=False, verbose_name="Možnost vleku")
    has_crane = models.BooleanField(default=False, verbose_name="Možnost ruky")
    vehicle_kinds = models.ManyToManyField(
        VehicleKindCatalog,
        blank=True,
        related_name="vehicle_profiles",
        verbose_name="Druhy vozidla",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Profil RZ vozidla"
        verbose_name_plural = "Profily RZ vozidel"
        ordering = ["rz__value"]

    def __str__(self):
        return f"{self.rz.value} - {self.vehicle_type or 'bez typu'}"
