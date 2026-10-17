from __future__ import annotations

from functools import lru_cache

from django.db import models
from django.db.utils import OperationalError, ProgrammingError


class AppSettings(models.Model):
    """Single-row app settings used across modules."""

    default_map_lat = models.DecimalField(max_digits=10, decimal_places=7, default=49.8175000)
    default_map_lng = models.DecimalField(max_digits=10, decimal_places=7, default=15.4730000)
    waste_docs_default_range_days = models.PositiveSmallIntegerField(
        default=90,
        verbose_name="Výchozí rozsah dnů pro seznam jízd",
        help_text="Počet dnů zpět pro předvyplnění filtru Od/Do na /waste-docs/.",
    )
    dashboard_tasks_notes = models.TextField(
        blank=True,
        verbose_name="Poznámky / úkoly na dashboardu",
        help_text="Interní text; denní připomínky na dashboardu jsou v modulu day_reminders.",
    )
    role_nav_defaults = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Horní lišta — výchozí podle rolí",
        help_text="Pro každou roli lze nastavit, zda uživatel s přepínačem „Dědit z role“ uvidí odkaz v menu. "
        "Výjimky u konkrétního uživatele zůstávají v /users/…/edit/.",
    )
    role_permission_defaults = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Oprávnění — výchozí podle rolí",
        help_text="Pro každou roli lze nastavit výchozí oprávnění (např. generování PIO). "
        "Uživatel s přepínačem „Dědit z role“ v /users/…/edit/ použije hodnotu odtud.",
    )
    svoz_disable_yard_daily_submit_limit = models.BooleanField(
        default=False,
        verbose_name="Vypnout denní limit odeslání matice ze sběrného dvora",
        help_text="Pokud zapnuté, kontrola „už dnes odesláno ze dvora“ se nebere v úvahu (bez mazání SvozTask). "
        "Pouze pro testování / vývoj — v produkci ponechte vypnuté.",
    )
    enforce_container_passport_move_check = models.BooleanField(
        default=True,
        verbose_name="Kontrolovat přistavení/stažení kontejneru podle pasportu",
        help_text="Pokud zapnuté, stejné číslo kontejneru nelze použít na více otevřených jízdách současně. "
        "Vypnutí povolí souběh i při shodném pasportu.",
    )
    customer_request_daily_cutoff_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Automatické uzavření požadavků (čas)",
        help_text=(
            "Po tomto čase se uzavře zadávání na následující den "
            "(např. dnes ve 13:00 se uzavře zítřek). Prázdné = vypnuto."
        ),
    )
    no_service_on_saturday = models.BooleanField(
        default=True,
        verbose_name="Sobota — nejezdíme",
        help_text="Nové požadavky a úkoly ze sběrného dvora se ze soboty posunou na další provozní den.",
    )
    no_service_on_sunday = models.BooleanField(
        default=True,
        verbose_name="Neděle — nejezdíme",
        help_text="Nové požadavky a úkoly ze sběrného dvora se z neděle posunou na další provozní den.",
    )
    session_idle_timeout_minutes = models.PositiveSmallIntegerField(
        default=30,
        verbose_name="Odhlásit po nečinnosti (minuty)",
        help_text=(
            "Po této době bez aktivity se uživatel odhlásí (dashboard i sběrné dvory). "
            "Platí od 5 do 480 minut."
        ),
    )
    popelar_hours_per_day = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=8,
        verbose_name="Popelář — hodin za den",
        help_text="Kolik hodin se počítá za jeden celý den nepřítomnosti typu Popelář (půlden = polovina).",
    )
    popelar_hourly_rate_czk = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Popelář — sazba Kč/h",
        help_text="Sazba za hodinu Popelář. Náklady v reportu = dny × hodiny × sazba.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Nastavení aplikace"
        verbose_name_plural = "Nastavení aplikace"

    @classmethod
    @lru_cache(maxsize=1)
    def _cached_load(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance

    @classmethod
    def load(cls):
        try:
            # Po rollbacku testovací transakce může zůstat v lru_cache instance
            # bez řádku v DB — při chybějícím záznamu cache vyčistit.
            if not cls.objects.filter(pk=1).exists():
                cls._cached_load.cache_clear()
            return cls._cached_load()
        except (OperationalError, ProgrammingError):
            # Graceful fallback during rolling deploy before DB migrations are applied.
            return cls(pk=1)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        type(self)._cached_load.cache_clear()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        type(self)._cached_load.cache_clear()
