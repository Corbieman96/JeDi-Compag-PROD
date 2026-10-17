# Generated manually

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("catalogs", "0042_subject_satellite_profiles"),
    ]

    operations = [
        migrations.CreateModel(
            name="DriverPortalPairingToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("secret", models.CharField(db_index=True, editable=False, max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Aktivní"), ("paused", "Pozastaveno"), ("revoked", "Zrušeno")],
                        default="active",
                        max_length=16,
                        verbose_name="Stav",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True, verbose_name="Zrušeno dne")),
                ("note", models.CharField(blank=True, max_length=200, verbose_name="Poznámka")),
                (
                    "driver",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portal_pairing_tokens",
                        to="catalogs.driverprofile",
                        verbose_name="Řidič",
                    ),
                ),
            ],
            options={
                "verbose_name": "Pozvánka portálu řidiče (QR)",
                "verbose_name_plural": "Pozvánky portálu řidiče (QR)",
                "ordering": ["-created_at"],
            },
        ),
    ]
