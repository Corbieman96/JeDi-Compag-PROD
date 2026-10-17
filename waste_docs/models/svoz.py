from django.conf import settings
from django.db import models

from catalogs.models import (
    ActivityCatalog,
    DriverProfile,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteTypeCatalog,
)


class SvozTask(models.Model):
    """Požadavek ze sběrného dvora — zobrazí se dispečerovi na dashboardu v cílový den."""

    class Status(models.TextChoices):
        OPEN = "open", "Otevřeno"
        DONE = "done", "Vyřízeno"

    subject_profile = models.ForeignKey(
        NameSubjectProfile,
        on_delete=models.CASCADE,
        related_name="svoz_tasks",
        verbose_name="Sběrný dvůr (subjekt)",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="svoz_tasks_created",
    )
    waste_type = models.ForeignKey(
        WasteTypeCatalog,
        on_delete=models.PROTECT,
        related_name="svoz_tasks",
    )
    suffix = models.ForeignKey(
        SuffixCatalog,
        on_delete=models.PROTECT,
        related_name="svoz_tasks",
    )
    vehicle_kind = models.ForeignKey(
        VehicleKindCatalog,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="svoz_tasks",
        verbose_name="Druh vozidla pro svoz",
        help_text="Z číselníku u páru subjektu; pro filtr RZ v průvodce.",
    )
    activity = models.ForeignKey(
        ActivityCatalog,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="svoz_tasks",
        verbose_name="Činnost",
        help_text="Z řádku matice v číselníku; předvyplnění průvodky.",
    )
    container_numbers = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Čísla kontejnerů",
        help_text="Více hodnot oddělte čárkou nebo středníkem.",
    )
    matrix_display_label = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Název řádku (zobrazení)",
        help_text="Kopie volitelného názvu z číselníku v době zařazení do fronty; nepřebírá roli koncovky ani druhu odpadu.",
    )
    source_waste_suffix_pair = models.ForeignKey(
        NameSubjectWasteSuffixPair,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="svoz_tasks",
        verbose_name="Řádek matice požadavku",
        help_text="Pár odpad–koncovka z matice sběrného dvora, ze kterého úkol vznikl.",
    )
    yard_contact_note = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Poznámka ze dvora",
        help_text="Z matice požadavku; při založení průvodky se přenese do pole Poznámka.",
    )
    target_date = models.DateField(db_index=True, verbose_name="Datum na dashboardu")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
        verbose_name="Stav",
    )
    resolved_pruvodka = models.ForeignKey(
        "Pruvodka",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="svoz_task_sources",
        verbose_name="Vyřízeno průvodkou",
    )
    assigned_driver = models.ForeignKey(
        DriverProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="svoz_tasks_assigned",
        verbose_name="Přiřazený řidič",
        help_text="Z denního plánu dvora (běžný nebo výjimky), nebo ručně z dashboardu.",
    )
    assigned_vehicle_rz = models.ForeignKey(
        VehicleRzCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="svoz_tasks_vehicle_rz",
        verbose_name="Přiřazené RZ vozidla",
        help_text="Z denního plánu svozů u slotu řidiče; předvyplnění průvodky.",
    )
    auto_pruvodka_last_error = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Poslední chyba auto-jízdy",
        help_text="Důvod, proč se po přiřazení řidiče nezaložila průvodka automaticky.",
    )
    auto_pruvodka_last_error_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Čas poslední chyby auto-jízdy",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Požadavek na svoz"
        verbose_name_plural = "Požadavky na svoz"
        indexes = [
            models.Index(fields=["target_date", "assigned_driver"]),
        ]

    def __str__(self):
        return f"Svoz {self.target_date} — {self.waste_type_id}/{self.suffix_id}"


class SvozYardDriverPlan(models.Model):
    """Denní přiřazení řidičů ke sběrnému dvoru pro daný den realizace (`target_date` úkolů)."""

    class RowKind(models.TextChoices):
        STANDARD = "standard", "Běžný svoz"
        EXCEPTION = "exception", "Výjimky (řádky matice mimo běžný plán)"

    plan_date = models.DateField(db_index=True, verbose_name="Den realizace")
    subject_profile = models.ForeignKey(
        NameSubjectProfile,
        on_delete=models.CASCADE,
        related_name="svoz_yard_driver_plans",
        verbose_name="Sběrný dvůr",
    )
    driver = models.ForeignKey(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name="svoz_yard_plans",
        verbose_name="Řidič",
    )
    vehicle_rz = models.ForeignKey(
        VehicleRzCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="svoz_yard_plan_rows",
        verbose_name="RZ vozidla",
        help_text="Povinné při vyplněném řidiči; musí odpovídat druhu vozidla u řádku (profil RZ).",
    )
    vehicle_rz_note = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Poznámka k vozidlu (RZ)",
        help_text="Volitelná poznámka dispečera u slotu plánu (např. návěs, poznámka k vozidlu).",
    )
    row_kind = models.CharField(
        max_length=16,
        choices=RowKind.choices,
        default=RowKind.STANDARD,
        db_index=True,
        verbose_name="Skupina plánu",
        help_text="Běžný fond dvora vs. výjimky pro řádky matice s vypnutým „běžným svozem“.",
    )
    vehicle_kind = models.ForeignKey(
        VehicleKindCatalog,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="svoz_yard_plans",
        verbose_name="Druh vozidla",
        help_text="Shoduje se s druhem vozidla u řádku matice; prázdné = starý plán bez rozlišení (přechod).",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Pořadí (round-robin)",
        help_text="Nižší číslo dříve v rotaci při stejném počtu úkolů.",
    )
    assignment_weight = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Podíl svozů",
        help_text="Váha slotu při rozdělování úkolů (např. 1 vs 3 pro poměr 1:3).",
    )

    class Meta:
        ordering = [
            "plan_date",
            "subject_profile",
            "row_kind",
            "vehicle_kind",
            "sort_order",
            "driver_id",
        ]
        verbose_name = "Plán svozu — řidič u dvora"
        verbose_name_plural = "Plán svozů — řidiči u dvorů"
        constraints = [
            models.UniqueConstraint(
                fields=["plan_date", "subject_profile", "row_kind", "vehicle_kind", "sort_order"],
                name="waste_docs_svozyardplan_uniq_date_subj_kind_vk_order",
            ),
        ]

    def __str__(self):
        return f"{self.plan_date} {self.subject_profile_id} → {self.driver_id}"


class SvozPlanDriverPoolAcknowledgement(models.Model):
    """
    Dispečer potvrdil, že je v pořádku nemít vyplněný fond řidičů v plánu
    pro daný den, dvůr, druh vozidla a skupinu (běžný svoz / výjimky).
    """

    plan_date = models.DateField(db_index=True, verbose_name="Den realizace")
    subject_profile = models.ForeignKey(
        NameSubjectProfile,
        on_delete=models.CASCADE,
        related_name="svoz_plan_pool_acks",
        verbose_name="Sběrný dvůr",
    )
    vehicle_kind = models.ForeignKey(
        VehicleKindCatalog,
        on_delete=models.CASCADE,
        related_name="svoz_plan_pool_acks",
        verbose_name="Druh vozidla",
    )
    row_kind = models.CharField(
        max_length=16,
        choices=SvozYardDriverPlan.RowKind.choices,
        verbose_name="Skupina plánu",
    )
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="svoz_plan_pool_acks",
        verbose_name="Potvrdil",
    )
    acknowledged_at = models.DateTimeField(auto_now_add=True, verbose_name="Čas potvrzení")

    class Meta:
        verbose_name = "Potvrzení výjimky plánu (bez fondu řidičů)"
        verbose_name_plural = "Potvrzení výjimek plánu (bez fondu řidičů)"
        constraints = [
            models.UniqueConstraint(
                fields=["plan_date", "subject_profile", "vehicle_kind", "row_kind"],
                name="waste_docs_svozpoolack_uniq_date_yard_vk_kind",
            ),
        ]

    def __str__(self):
        return f"{self.plan_date} yard={self.subject_profile_id} vk={self.vehicle_kind_id}"
