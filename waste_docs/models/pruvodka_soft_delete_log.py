from django.conf import settings
from django.db import models


class PruvodkaSoftDeleteLog(models.Model):
    pruvodka = models.ForeignKey(
        "waste_docs.Pruvodka",
        on_delete=models.PROTECT,
        related_name="soft_delete_logs",
        verbose_name="Jízda",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pruvodka_soft_delete_logs",
        verbose_name="Smazal",
    )
    deleted_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Smazáno")
    reason = models.CharField(max_length=500, verbose_name="Důvod smazání")

    snd_cislo_listu = models.CharField(max_length=32, blank=True, verbose_name="Číslo listu (snapshot)")
    drive_date = models.DateField(null=True, blank=True, db_index=True, verbose_name="Datum jízdy")
    name_snapshot = models.CharField(max_length=255, blank=True, verbose_name="Název F/P")
    vehicle_rz_snapshot = models.CharField(max_length=20, blank=True, verbose_name="RZ")
    driver_snapshot = models.CharField(max_length=255, blank=True, verbose_name="Řidič")
    activity_snapshot = models.CharField(max_length=120, blank=True, verbose_name="Činnost")

    class Meta:
        ordering = ["-deleted_at", "-id"]
        verbose_name = "Záznam smazané jízdy"
        verbose_name_plural = "Záznamy smazaných jízd"
        indexes = [
            models.Index(fields=["-deleted_at", "snd_cislo_listu"]),
        ]

    def __str__(self):
        snd = (self.snd_cislo_listu or "").strip() or f"#{self.pruvodka_id}"
        return f"{snd} ({self.deleted_at:%d.%m.%Y %H:%M})"
