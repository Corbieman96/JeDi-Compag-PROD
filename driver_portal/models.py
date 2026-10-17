import secrets

from django.db import models


class DriverPortalPairingToken(models.Model):
    """Jednorázové nebo dlouhodobé propojení účtu s DriverProfile přes QR (tajný řetězec v URL)."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Aktivní"
        PAUSED = "paused", "Pozastaveno"
        REVOKED = "revoked", "Zrušeno"

    driver = models.ForeignKey(
        "catalogs.DriverProfile",
        on_delete=models.CASCADE,
        related_name="portal_pairing_tokens",
        verbose_name="Řidič",
    )
    secret = models.CharField(max_length=64, unique=True, db_index=True, editable=False)
    display_code = models.CharField(
        max_length=14,
        unique=True,
        db_index=True,
        editable=False,
        verbose_name="Párovací kód",
        help_text="Zobrazí se řidiči a v číselníku; ověření správné pozvánky vedle QR.",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="Stav",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True, verbose_name="Zrušeno dne")
    note = models.CharField(max_length=200, blank=True, verbose_name="Poznámka")

    class Meta:
        verbose_name = "Pozvánka portálu řidiče (QR)"
        verbose_name_plural = "Pozvánky portálu řidiče (QR)"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.secret:
            self.secret = secrets.token_urlsafe(32)
        if not self.display_code:
            from driver_portal.services.display_code import generate_unique_display_code

            self.display_code = generate_unique_display_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Pozvánka #{self.pk} — řidič {self.driver_id}"
