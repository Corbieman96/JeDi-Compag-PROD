import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0050_pruvodka_updated_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("waste_docs", "0056_rename_weight_kg_to_weight_t"),
    ]

    operations = [
        migrations.CreateModel(
            name="YardSvozSubmissionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("submitted_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Čas odeslání")),
                ("submission_day", models.DateField(db_index=True, verbose_name="Den odeslání")),
                ("display_label", models.CharField(blank=True, max_length=200, verbose_name="Název řádku")),
                ("container_numbers", models.CharField(blank=True, max_length=500, verbose_name="Kontejner(y)")),
                ("yard_contact_note", models.CharField(blank=True, max_length=200, verbose_name="Poznámka ze dvora")),
                ("is_hazardous", models.BooleanField(default=False, verbose_name="Nebezpečný odpad")),
                ("target_date", models.DateField(blank=True, null=True, verbose_name="Cílový den na dashboardu")),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="yard_svoz_submission_logs_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "source_waste_suffix_pair",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="svoz_submission_logs",
                        to="catalogs.namesubjectwastesuffixpair",
                        verbose_name="Řádek matice",
                    ),
                ),
                (
                    "subject_profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="svoz_submission_logs",
                        to="catalogs.namesubjectprofile",
                        verbose_name="Sběrný dvůr (subjekt)",
                    ),
                ),
                (
                    "suffix",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="yard_svoz_submission_logs",
                        to="catalogs.suffixcatalog",
                    ),
                ),
                (
                    "vehicle_kind",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="yard_svoz_submission_logs",
                        to="catalogs.vehiclekindcatalog",
                        verbose_name="Druh vozidla",
                    ),
                ),
                (
                    "waste_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="yard_svoz_submission_logs",
                        to="catalogs.wastetypecatalog",
                    ),
                ),
            ],
            options={
                "verbose_name": "Log odeslání matice svozu",
                "verbose_name_plural": "Logy odeslání matice svozu",
                "ordering": ["-submitted_at", "-pk"],
                "indexes": [
                    models.Index(fields=["subject_profile", "submission_day"], name="waste_docs__subject_8a1f2d_idx"),
                ],
            },
        ),
    ]
