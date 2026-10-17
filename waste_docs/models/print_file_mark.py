from __future__ import annotations

from django.conf import settings
from django.db import models


class PrintFileMark(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="print_file_marks",
    )
    drive_date = models.DateField("Datum jízdy")
    row_key = models.CharField(max_length=255)
    printed_at = models.DateTimeField(auto_now=True)
    is_current = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "drive_date", "row_key"),
                name="uniq_print_file_mark_user_date_row",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "drive_date")),
            models.Index(fields=("is_current", "drive_date"), name="waste_docs__is_curr_7a1b2c_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.drive_date} {self.row_key}"
