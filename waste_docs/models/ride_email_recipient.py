from __future__ import annotations

from django.conf import settings
from django.db import models


class RideEmailRecipient(models.Model):
    email = models.EmailField("E-mail příjemce", max_length=254, unique=True)
    label = models.CharField("Popisek", max_length=120, blank=True)
    last_used_at = models.DateTimeField("Naposledy použito", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ride_email_recipients_created",
        verbose_name="Vytvořil",
    )

    class Meta:
        verbose_name = "Uložený příjemce e-mailu jízdy"
        verbose_name_plural = "Uložení příjemci e-mailu jízdy"
        ordering = ("-last_used_at", "email")

    def __str__(self) -> str:
        if self.label:
            return f"{self.label} <{self.email}>"
        return self.email

    @property
    def display_label(self) -> str:
        if self.label:
            return f"{self.label} ({self.email})"
        return self.email
