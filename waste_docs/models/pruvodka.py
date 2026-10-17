import os

from django.conf import settings
from django.db import models
from django.utils import timezone

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    ContainerPassport,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)


class Pruvodka(models.Model):
    class Status(models.TextChoices):
        RECORDED = "recorded", "Založeno"
        GENERATED = "generated", "Vygenerováno"

    activity = models.ForeignKey(
        ActivityCatalog,
        on_delete=models.PROTECT,
        related_name="pruvodky",
        null=True,
        blank=True,
    )
    name = models.ForeignKey(NameCatalog, on_delete=models.PROTECT, related_name="pruvodky")
    ico = models.ForeignKey(IcoCatalog, on_delete=models.PROTECT, related_name="pruvodky")
    address = models.ForeignKey(AddressCatalog, on_delete=models.PROTECT, related_name="pruvodky")
    waste_type = models.ForeignKey(WasteTypeCatalog, on_delete=models.PROTECT, related_name="pruvodky")
    waste_code = models.ForeignKey(WasteCodeCatalog, on_delete=models.PROTECT, related_name="pruvodky")
    waste_category = models.ForeignKey(WasteCategoryCatalog, on_delete=models.PROTECT, related_name="pruvodky")
    vehicle_rz = models.ForeignKey(
        VehicleRzCatalog,
        on_delete=models.PROTECT,
        related_name="pruvodky",
        null=True,
        blank=True,
    )
    container_passport = models.ForeignKey(
        ContainerPassport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pruvodky",
        verbose_name="Pasport kontejneru",
    )
    driver = models.ForeignKey(
        DriverProfile,
        on_delete=models.PROTECT,
        related_name="pruvodky",
        null=True,
        blank=True,
    )
    suffix = models.ForeignKey(
        SuffixCatalog,
        on_delete=models.PROTECT,
        related_name="pruvodky",
        null=True,
        blank=True,
    )
    source_waste_suffix_pair = models.ForeignKey(
        NameSubjectWasteSuffixPair,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pruvodky",
        verbose_name="Řádek matice (odpad–koncovka)",
        help_text="Konkrétní řádek z „Povolené odpady a koncovky“ u subjektu pro tuto jízdu.",
    )
    drive_date = models.DateField(default=timezone.localdate, verbose_name="Datum jízdy", db_index=True)
    ride_group_number = models.PositiveIntegerField(default=0, editable=False)
    ride_sequence = models.PositiveIntegerField(default=1, editable=False)
    ride_route_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
        verbose_name="Pořadí v trase jízdy",
        help_text="0 = výchozí (podle ride_sequence). Nastavuje se ručním seřazením na dashboardu.",
    )
    snd_cislo_listu = models.CharField(max_length=32, blank=True, editable=False)

    container_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Číslo kontejneru (1)",
    )
    container_number_2 = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Číslo kontejneru (2)",
        help_text="Druhý kontejner při výměně (např. stažený).",
    )
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name="Telefon")
    contract_number = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Číslo smlouvy",
    )
    contact_note = models.CharField(max_length=200, blank=True, verbose_name="Poznámka")
    weight_t = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="Hmotnost (t)",
    )

    # Denormalized snapshots keep historical values even if catalogs change later.
    name_snapshot = models.CharField(max_length=255, blank=True)
    ico_snapshot = models.CharField(max_length=8, blank=True)
    address_snapshot = models.CharField(max_length=255, blank=True)
    waste_type_snapshot = models.CharField(max_length=255, blank=True)
    waste_code_snapshot = models.CharField(max_length=20, blank=True)
    waste_category_snapshot = models.CharField(max_length=20, blank=True)
    vehicle_rz_snapshot = models.CharField(max_length=20, blank=True)
    driver_snapshot = models.CharField(max_length=255, blank=True)
    contract_number_snapshot = models.CharField(max_length=120, blank=True)
    suffix_snapshot = models.CharField(max_length=50, blank=True)
    container_snapshot_2 = models.CharField(max_length=50, blank=True)
    activity_snapshot = models.CharField(max_length=120, blank=True)
    weight_snapshot = models.CharField(
        max_length=32,
        blank=True,
        verbose_name="Hmotnost — snapshot pro Excel",
    )

    follow_up_open = models.BooleanField(
        default=False,
        verbose_name="Čeká na navazující jízdu",
        help_text="Nastaveno podle činnosti a návaznosti; po propojení s druhou průvodkou se vypne.",
    )
    follow_up_parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="follow_up_children",
        verbose_name="Navazuje na jízdu",
    )
    follow_up_resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Návaznost vyřízena",
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECORDED)
    generated_file = models.FileField(upload_to="pruvodky/", blank=True, null=True)
    zpo_instance_file = models.FileField(
        upload_to="pruvodky/zpo_instance/",
        blank=True,
        null=True,
        verbose_name="ZPO pro tuto jízdu",
        help_text="Vygenerováno ze vzoru v číselníku; obsahuje číslo listu/jízdy.",
    )
    zpo_instance_for_snd = models.CharField(
        max_length=32,
        blank=True,
        editable=False,
        verbose_name="Číslo vložené do ZPO",
    )
    zpo_generator_revision = models.PositiveSmallIntegerField(
        default=0,
        editable=False,
        verbose_name="Revize generátoru ZPO",
        help_text="Při zvýšení v kódu se soubor ZPO znovu vygeneruje.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pruvodky",
    )
    is_blank_pruvodka = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Bianko průvodka",
        help_text="Nouzová prázdná průvodka se SND; údaje se doplní později nebo se archivuje nepoužitá.",
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Archivováno",
    )
    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Archivováno dne",
    )
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="archived_pruvodky",
        verbose_name="Archivoval",
    )
    archive_reason = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Důvod archivace",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    driver_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Dokončeno řidičem",
        help_text="Volitelný čas označení jízdy jako vyřízené z portálu řidiče.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Jízda"
        verbose_name_plural = "Jízdy"
        constraints = [
            models.UniqueConstraint(
                fields=["drive_date", "snd_cislo_listu"],
                condition=models.Q(snd_cislo_listu__gt="") & models.Q(is_archived=False),
                name="waste_docs_pruvodka_uniq_drive_date_snd_nonempty",
            ),
        ]

    def __str__(self):
        return f"Jízda #{self.pk or 'nová'} ({self.snd_cislo_listu or self.status})"

    @property
    def follow_up_is_stazeni_style(self) -> bool:
        from waste_docs.follow_up_display import is_stazeni_style_follow_up

        return is_stazeni_style_follow_up(self)

    @staticmethod
    def _format_snd(group_number: int, year: int, sequence: int) -> str:
        from waste_docs.services.ride_numbering import format_snd

        return format_snd(group_number, year, sequence)

    def save(self, *args, **kwargs):
        from waste_docs.services.ride_numbering import apply_pruvodka_pre_save

        apply_pruvodka_pre_save(self)
        super().save(*args, **kwargs)


def pruvodka_attachment_upload_to(instance, filename: str) -> str:
    ride_id = instance.pruvodka_id or "new"
    return f"pruvodka_attachments/{ride_id}/{filename}"


class PruvodkaAttachment(models.Model):
    pruvodka = models.ForeignKey(
        Pruvodka,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="Jízda",
    )
    sort_order = models.PositiveSmallIntegerField(default=1, verbose_name="Pořadí")
    file = models.FileField(upload_to=pruvodka_attachment_upload_to, verbose_name="Příloha")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Příloha jízdy"
        verbose_name_plural = "Přílohy jízdy"

    def __str__(self):
        return f"Příloha #{self.pk} k jízdě #{self.pruvodka_id}"

    @property
    def filename_display(self) -> str:
        return os.path.basename(self.file.name or "")
