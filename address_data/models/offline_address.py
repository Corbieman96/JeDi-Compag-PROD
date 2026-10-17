from django.db import models


class OfflineAddress(models.Model):
    city = models.CharField(max_length=120, blank=True)
    street = models.CharField(max_length=160, blank=True)
    house_number = models.CharField(max_length=32, blank=True)
    postal_code = models.CharField(max_length=16, blank=True)
    label = models.CharField(max_length=255)
    lat = models.DecimalField(max_digits=10, decimal_places=7)
    lng = models.DecimalField(max_digits=10, decimal_places=7)
    city_norm = models.CharField(max_length=120, db_index=True)
    street_norm = models.CharField(max_length=160, db_index=True)
    label_norm = models.CharField(max_length=255, db_index=True)

    class Meta:
        ordering = ("label",)
        indexes = [
            models.Index(fields=("city_norm", "street_norm"), name="addr_city_street_idx"),
            models.Index(fields=("label_norm",), name="addr_label_idx"),
        ]

    def __str__(self):
        return self.label

    @property
    def postal_code_display(self) -> str:
        digits = "".join(ch for ch in (self.postal_code or "") if ch.isdigit())
        if len(digits) == 5:
            return f"{digits[:3]} {digits[3:]}"
        return self.postal_code or ""

    @property
    def street_with_number(self) -> str:
        return " ".join(part for part in [self.street, self.house_number] if part).strip()
