from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .driver import DriverProfile


class DriverAbsence(models.Model):
    class AbsenceType(models.TextChoices):
        GARBAGE = "garbage", "Popelář"
        VACATION = "vacation", "Dovolená"
        SICK = "sick", "Nemoc"
        DOCTOR = "doctor", "Lékař / vyšetření"
        COMPENSATORY_LEAVE = "compensatory_leave", "Náhradní volno"
        WEDDING = "wedding", "Svatba"
        FUNERAL = "funeral", "Pohřeb"
        PATERNITY = "paternity", "Otcovská"
        MATERNITY_PARENTAL = "maternity_parental", "Mateřská / rodičovská"
        TRAINING = "training", "Školení"
        OBSTACLE = "obstacle", "Překážky v práci (§)"
        BLOOD_DONOR = "blood_donor", "Krev / dárce"
        OCR = "ocr", "OČR"
        UNPAID_LEAVE = "unpaid_leave", "Neplacené volno"
        OTHER = "other", "Jiné"

    driver = models.ForeignKey(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name="absences",
        verbose_name="Řidič",
    )
    absence_type = models.CharField(
        max_length=32,
        choices=AbsenceType.choices,
        verbose_name="Důvod nepřítomnosti",
    )
    date_from = models.DateField(verbose_name="Od")
    date_to = models.DateField(verbose_name="Do")
    is_partial = models.BooleanField(
        default=False,
        verbose_name="Půldenní",
        help_text="Pouze u dovolené nebo nemoci — řidič zůstane v nabídce a v panelu Řidiči.",
    )
    available_for_transport = models.BooleanField(
        default=False,
        verbose_name="Doprava",
        help_text=(
            "Jen u Popeláře — řidič zůstane v panelu Řidiči a v nabídce na jízdu "
            "(např. skok na auto), přestože je vedený jako Popelář."
        ),
    )
    note = models.TextField(blank=True, verbose_name="Poznámka")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driver_absences_created",
        verbose_name="Zadal",
    )

    class Meta:
        verbose_name = "Nepřítomnost řidiče"
        verbose_name_plural = "Nepřítomnosti řidičů"
        ordering = ["-date_from", "-date_to", "driver_id"]
        indexes = [
            models.Index(fields=["date_from", "date_to"]),
        ]

    def __str__(self):
        return f"{self.driver} — {self.get_absence_type_display()} ({self.date_from}–{self.date_to})"

    def clean(self):
        super().clean()
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError("Datum „od“ musí být před nebo stejné jako „do“.")
        partial_ok = self.absence_type in (
            self.AbsenceType.GARBAGE,
            self.AbsenceType.VACATION,
            self.AbsenceType.SICK,
            self.AbsenceType.DOCTOR,
            self.AbsenceType.OBSTACLE,
        )
        if self.is_partial and not partial_ok:
            raise ValidationError(
                {
                    "is_partial": (
                        "Půldenní nepřítomnost lze zvolit jen u: Popelář, Dovolená, "
                        "Nemoc, Lékař / vyšetření, Překážky v práci."
                    )
                }
            )
