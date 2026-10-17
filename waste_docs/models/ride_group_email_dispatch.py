from __future__ import annotations

from django.conf import settings
from django.db import models


class RideGroupEmailDispatch(models.Model):
    drive_date = models.DateField("Datum jízdy")
    vehicle_rz = models.ForeignKey(
        "catalogs.VehicleRzCatalog",
        on_delete=models.CASCADE,
        related_name="email_dispatches",
    )
    recipient_email = models.EmailField("E-mail příjemce")
    subject = models.CharField(max_length=255)
    ride_count = models.PositiveSmallIntegerField(default=0)
    attachment_count = models.PositiveSmallIntegerField(default=2)
    dispatched_at = models.DateTimeField(auto_now=True)
    dispatched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ride_group_email_dispatches",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("drive_date", "vehicle_rz"),
                name="uniq_ride_group_email_dispatch_date_rz",
            ),
        ]
        indexes = [
            models.Index(fields=("drive_date", "vehicle_rz")),
        ]

    def __str__(self) -> str:
        return f"{self.drive_date} RZ#{self.vehicle_rz_id} → {self.recipient_email}"
