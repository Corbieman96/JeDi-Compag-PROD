from django.db import models

from .vehicle_rz import VehicleKindCatalog


class ActivityCatalog(models.Model):
    name = models.CharField(max_length=120, unique=True, verbose_name="Druh činnosti")
    vehicle_kinds = models.ManyToManyField(
        VehicleKindCatalog,
        blank=True,
        related_name="activities",
        verbose_name="Číselník druhů vozidel",
    )
    follow_up_activity = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preceding_activities",
        verbose_name="Hlídat dokončení činnosti",
        help_text="Po této činnosti systém může evidovat otevřenou návaznost (např. Přistavit → Stažení).",
    )
    follow_up_activities = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        related_name="preceding_activities_multi",
        verbose_name="Možnosti dokončení činnosti",
        help_text="Volitelně více navazujících činností (např. Přistavit → Stažení nebo Výměna).",
    )
    follow_up_terminal_activities = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        related_name="terminal_for_preceding",
        verbose_name="Uzavírají návaznost",
        help_text="Které z navazujících činností případ definitivně uzavřou (např. Stažení). Ostatní jen evidují mezikrok (Výměna).",
    )
    follow_up_symbol_parent = models.CharField(
        max_length=8,
        blank=True,
        verbose_name="Symbol návaznosti k předchozí jízdě",
        help_text="Ve sloupci Návaznost u průvodky navázané na předchozí záznam (např. ⇄ nebo ↕). Prázdné = výchozí šipka nahoru.",
    )
    follow_up_symbol_child = models.CharField(
        max_length=8,
        blank=True,
        verbose_name="Symbol k navazujícím jízdám",
        help_text="U průvodky, na kterou už něco navazuje — před čísly navazujících záznamů (např. ⇅). Prázdné = výchozí šipka dolů.",
    )
    require_nitropodnikovy_subjekt = models.BooleanField(
        default=False,
        verbose_name="Vyžadovat nitropodnikový subjekt",
        help_text="U průvodky s touto činností musí být subjekt označen jako nitropodnikový a nesmí jít o čistě obec.",
    )
    evidence_without_excel = models.BooleanField(
        default=False,
        verbose_name="Stačí evidence v databázi (bez Excelu)",
        help_text="U průvodek této činnosti se nezobrazí generování Excelu a tisk jízdy jej nevyžaduje.",
    )
    visible_for_submitter = models.BooleanField(
        default=True,
        verbose_name="Viditelné pro zadavatele",
        help_text="Určuje, zda se činnost nabízí při zakládání zákaznického požadavku.",
    )
    default_service_minutes = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Výchozí délka zastávky (min)",
        help_text="Odhad času auta na místě pro AI prompt řazení trasy; lze doladit ručně.",
    )

    class Meta:
        verbose_name = "Činnost"
        verbose_name_plural = "Činnosti"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def follow_up_activity_ids_allowed(self) -> list[int]:
        ids = list(self.follow_up_activities.values_list("id", flat=True))
        if ids:
            return ids
        if self.follow_up_activity_id:
            return [self.follow_up_activity_id]
        return []

    def primary_follow_up_activity(self):
        if self.follow_up_activity_id:
            return self.follow_up_activity
        return self.follow_up_activities.order_by("name", "pk").first()
