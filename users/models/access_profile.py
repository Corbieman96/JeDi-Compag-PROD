from django.conf import settings
from django.db import models


class UserAccessProfile(models.Model):
    """Per-user přístup: úprava uložených průvodky a viditelnost položek menu."""

    class NavOverride(models.TextChoices):
        INHERIT = "inherit", "Dědit z role"
        SHOW = "show", "Vždy zobrazit"
        HIDE = "hide", "Skrýt"

    class PioExportOverride(models.TextChoices):
        INHERIT = "inherit", "Dědit z role"
        SHOW = "show", "Vždy povolit"
        HIDE = "hide", "Vypnout"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="access_profile",
    )
    can_edit_existing_pruvodka = models.BooleanField(
        default=False,
        verbose_name="Smí upravovat existující průvodky",
        help_text="Platí pro průvodky, které uživatel smí vidět (vlastní nebo všechny podle role).",
    )
    can_create_pruvodka = models.BooleanField(
        default=True,
        verbose_name="Smí založit novou jízdu",
        help_text="Tlačítko Nová jízda, formulář, založení ze sběrného dvora i automatické založení z úkolu svozu.",
    )
    can_delete_all_pruvodky = models.BooleanField(
        default=False,
        verbose_name="Smí smazat všechny průvodky",
        help_text="Pouze pro admina; povolí hromadné smazání všech průvodek na stránce /waste-docs/.",
    )
    can_manage_dashboard_notes = models.BooleanField(
        default=True,
        verbose_name="Smí přidávat a upravovat denní poznámky",
        help_text="Panel „Poslední úkoly / poznámky“ na dashboardu — nová poznámka, úprava, mazání a promazání.",
    )
    nav_dashboard = models.CharField(
        max_length=16,
        choices=NavOverride.choices,
        default=NavOverride.INHERIT,
        verbose_name="Menu: Dashboard",
    )
    nav_pruvodky = models.CharField(
        max_length=16,
        choices=NavOverride.choices,
        default=NavOverride.INHERIT,
        verbose_name="Menu: Průvodky",
    )
    nav_customer_requests = models.CharField(
        max_length=16,
        choices=NavOverride.choices,
        default=NavOverride.INHERIT,
        verbose_name="Menu: Požadavky",
    )
    nav_invoice_queue = models.CharField(
        max_length=16,
        choices=NavOverride.choices,
        default=NavOverride.INHERIT,
        verbose_name="Menu: Schvalování záloh",
    )
    nav_catalogs = models.CharField(
        max_length=16,
        choices=NavOverride.choices,
        default=NavOverride.INHERIT,
        verbose_name="Menu: Číselníky",
    )
    nav_settings = models.CharField(
        max_length=16,
        choices=NavOverride.choices,
        default=NavOverride.INHERIT,
        verbose_name="Menu: Nastavení",
    )
    nav_address_data = models.CharField(
        max_length=16,
        choices=NavOverride.choices,
        default=NavOverride.INHERIT,
        verbose_name="Menu: Adresy (offline)",
    )
    nav_reports = models.CharField(
        max_length=16,
        choices=NavOverride.choices,
        default=NavOverride.INHERIT,
        verbose_name="Menu: Reporty",
    )
    catalog_item_nav = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Číselníky — viditelnost řádků",
        help_text="Klíč = slug číselníku (viz přehled), hodnota inherit/show/hide. "
        "Prázdné = vše dědit (zobrazit).",
    )
    sberny_dvur_subject = models.ForeignKey(
        "catalogs.NameSubjectProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_user_access_profiles",
        verbose_name="Subjekt sběrného dvora",
        help_text="Z číselníku F/P osoby — povinné pro roli „Sběrný dvůr“ (požadavky na svoz).",
    )
    can_toggle_subject_is_municipality = models.BooleanField(
        default=False,
        verbose_name="Smí měnit: Jedná se o obec",
    )
    can_toggle_subject_collection_yard = models.BooleanField(
        default=False,
        verbose_name="Smí měnit: Lokalita sběrného dvora",
    )
    can_toggle_subject_yard_allow_pruvodka = models.BooleanField(
        default=False,
        verbose_name="Smí měnit: Povolit průvodku z dvora",
    )
    can_toggle_subject_yard_allow_matrix = models.BooleanField(
        default=False,
        verbose_name="Smí měnit: Povolit matici požadavků",
    )
    can_toggle_subject_dispatch_group = models.BooleanField(
        default=False,
        verbose_name="Smí měnit: Skupina v plánu svozů",
    )
    can_toggle_subject_nitropodnikovy = models.BooleanField(
        default=False,
        verbose_name="Smí měnit: Nitropodnikový subjekt",
    )
    can_toggle_subject_system_generates_zpo = models.BooleanField(
        default=True,
        verbose_name="Smí měnit: Generovat systémové ZPO k jízdám",
    )
    export_pio_profile = models.CharField(
        max_length=16,
        choices=PioExportOverride.choices,
        default=PioExportOverride.INHERIT,
        verbose_name="PIO — profilová šablona u subjektu F/P",
        help_text="Tlačítko Vygenerovat PIO na úpravě subjektu v číselníku jmen. "
        "Superuser má vždy přístup; ostatní dědí z Nastavení podle role, pokud je zde „Dědit z role“.",
    )
    driver_profile = models.ForeignKey(
        "catalogs.DriverProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_user_access_profiles",
        verbose_name="Propojený řidič (portál)",
        help_text="Účet s rolí „Řidič“ — data v portálu jen pro tento profil. Lze doplnit QR pozvánkou.",
    )

    class Meta:
        verbose_name = "Přístup uživatele"
        verbose_name_plural = "Přístupy uživatelů"
        constraints = [
            models.UniqueConstraint(
                fields=["driver_profile"],
                condition=models.Q(driver_profile__isnull=False),
                name="useraccessprofile_driver_profile_id_uniq_when_set",
            ),
        ]

    def __str__(self):
        return f"Přístup: {self.user_id}"
