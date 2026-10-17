from django.db import models


class ActivityFieldMode(models.TextChoices):
    OFF = "off", "Skryté / nepoužívat"
    OPTIONAL = "optional", "Volitelné"
    REQUIRED = "required", "Povinné"


class ActivityFieldKey(models.TextChoices):
    SUFFIX = "suffix", "Koncovka"
    WASTE_TYPE = "waste_type", "Druh odpadu"
    NAME = "name", "Subjekt (F/P osoba)"
    FULFILLMENT_ADDRESS = "fulfillment_address", "Adresa plnění"
    DRIVER = "driver", "Řidič"
    VEHICLE_RZ = "vehicle_rz", "RZ vozidla"
    CONTAINER_1 = "container_1", "Číslo kontejneru (1)"
    CONTAINER_2 = "container_2", "Číslo kontejneru (2) — druhý při výměně"
    CONTACT_PHONE = "contact_phone", "Telefon"
    CONTRACT_NUMBER = "contract_number", "Číslo smlouvy"
    CONTACT_NOTE = "contact_note", "Poznámka"
    SND_CISLO = "snd_cislo", "Číslo listu / SND"
    ZPO = "zpo", "Generování ZPO"
    PIO = "pio", "PIO dokument"


class ActivityFieldRule(models.Model):
    """Režim evidence pole na průvodce pro danou činnost. Chybějící řádek = výchozí z kódu."""

    activity = models.ForeignKey(
        "catalogs.ActivityCatalog",
        on_delete=models.CASCADE,
        related_name="field_rules",
    )
    field_key = models.CharField(max_length=32, choices=ActivityFieldKey.choices)
    mode = models.CharField(max_length=16, choices=ActivityFieldMode.choices)

    class Meta:
        verbose_name = "Pravidlo pole činnosti"
        verbose_name_plural = "Pravidla polí činnosti"
        constraints = [
            models.UniqueConstraint(fields=["activity", "field_key"], name="uniq_activity_field_rule"),
        ]

    def __str__(self):
        return f"{self.activity} — {self.get_field_key_display()}: {self.get_mode_display()}"
