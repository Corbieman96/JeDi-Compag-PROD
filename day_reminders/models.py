from django.conf import settings
from django.db import models

from day_reminders.card_colors import CardColor


class DayReminder(models.Model):
    class Kind(models.TextChoices):
        ONE_OFF = "one_off", "Jednorázová"
        WEEKLY = "weekly", "Týdně"
        MONTHLY = "monthly", "Měsíčně"
        ROLLING = "rolling", "Přenášet do vyřešení"

    title = models.CharField("Název", max_length=160)
    text = models.TextField("Text", blank=True)
    card_color = models.CharField(
        "Barva karty",
        max_length=16,
        choices=CardColor.choices,
        default=CardColor.YELLOW,
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, db_index=True)

    class NoteGroup(models.TextChoices):
        REQUEST = "request", "Požadavek"
        OTHER = "other", "Ostatní"

    note_group = models.CharField(
        "Druh poznámky",
        max_length=16,
        choices=NoteGroup.choices,
        default=NoteGroup.REQUEST,
        db_index=True,
        help_text="Rozlišení pro tisk: Požadavek vs Ostatní.",
    )

    pinned_date = models.DateField("Datum (jednorázová)", null=True, blank=True)
    repeat_weekdays = models.JSONField(
        "Dny v týdnu (0=Po … 6=Ne)",
        default=list,
        blank=True,
        help_text="U týdenní připomínky seznam čísel 0–6, např. [0,2,4] pro Po, St, Pá.",
    )
    repeat_monthly = models.JSONField(
        "Měsíční pravidlo",
        default=dict,
        blank=True,
        help_text='{"ordinal": 1, "weekday": 2} — např. každá 1. středa; ordinal -1 = poslední výskyt.',
    )
    repeat_active_from = models.DateField("Opakování platné od", null=True, blank=True)
    repeat_active_until = models.DateField("Opakování platné do", null=True, blank=True)

    rolling_start = models.DateField("Začátek přenášení", null=True, blank=True)

    snoozed_until = models.DateField("Skrýt do", null=True, blank=True)
    completed_at = models.DateTimeField("Vyřešeno", null=True, blank=True, db_index=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="day_reminders_created",
    )
    source_svoz_task = models.ForeignKey(
        "waste_docs.SvozTask",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="yard_dispatch_notes",
        verbose_name="Zdroj — hlášení ze sběrného dvora",
        help_text="Poznámka vytvořená automaticky po odeslání matice ze sběrného dvora.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=("kind", "pinned_date")),
            models.Index(fields=("rolling_start",)),
        ]

    def __str__(self):
        return (self.title or "")[:80]

    def weekly_weekday_set(self) -> set[int]:
        """Pro kind=weekly množina dnů (weekday) 0..6."""
        raw = self.repeat_weekdays or []
        out: set[int] = set()
        for x in raw:
            try:
                n = int(x)
                if 0 <= n <= 6:
                    out.add(n)
            except (TypeError, ValueError):
                continue
        return out

    def repeat_weekdays_display(self) -> str:
        if self.kind != self.Kind.WEEKLY:
            return ""
        from day_reminders.services.queries import WEEKDAY_CHOICES

        m = dict(WEEKDAY_CHOICES)
        parts = [m.get(n, "?") for n in sorted(self.weekly_weekday_set())]
        return ", ".join(parts)

    def repeat_monthly_display(self) -> str:
        if self.kind != self.Kind.MONTHLY:
            return ""
        from day_reminders.services.monthly_recurrence import monthly_display

        return monthly_display(self.repeat_monthly)


class DayReminderException(models.Model):
    """Přesun jednoho výskytu týdenní připomínky na jiný kalendářní den."""

    reminder = models.ForeignKey(
        DayReminder,
        on_delete=models.CASCADE,
        related_name="exceptions",
    )
    original_date = models.DateField("Původní datum výskytu")
    rescheduled_to = models.DateField("Přesunuto na")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("reminder", "original_date"),
                name="unique_dayreminder_exception_original",
            ),
        ]


class DayReminderCompletion(models.Model):
    """Vyřešení připomínky pro konkrétní kalendářní den."""

    reminder = models.ForeignKey(
        DayReminder,
        on_delete=models.CASCADE,
        related_name="completions",
    )
    resolved_on = models.DateField("Vyřešeno pro den", db_index=True)
    resolved_at = models.DateTimeField("Čas označení", auto_now_add=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="day_reminder_completions",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("reminder", "resolved_on"),
                name="unique_dayreminder_completion_per_day",
            ),
        ]
