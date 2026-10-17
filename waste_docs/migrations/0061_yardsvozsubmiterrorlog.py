from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0061_ensure_namesubjectwastesuffixpair_ride_note"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("waste_docs", "0060_pruvodka_snd_unique_exclude_archived"),
    ]

    operations = [
        migrations.CreateModel(
            name="YardSvozSubmitErrorLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Čas")),
                ("submission_day", models.DateField(db_index=True, verbose_name="Den")),
                ("message", models.TextField(verbose_name="Text chyby")),
                ("display_label", models.CharField(blank=True, max_length=200, verbose_name="Řádek matice")),
                ("container_numbers", models.CharField(blank=True, max_length=500, verbose_name="Kontejner(y)")),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True, verbose_name="Přečteno")),
                (
                    "acknowledged_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="yard_svoz_submit_error_logs_acked",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="yard_svoz_submit_error_logs_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "subject_profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="svoz_submit_error_logs",
                        to="catalogs.namesubjectprofile",
                        verbose_name="Sběrný dvůr (subjekt)",
                    ),
                ),
            ],
            options={
                "verbose_name": "Chyba odeslání matice svozu",
                "verbose_name_plural": "Chyby odeslání matice svozu",
                "ordering": ["-created_at", "-pk"],
            },
        ),
        migrations.AddIndex(
            model_name="yardsvozsubmiterrorlog",
            index=models.Index(fields=["subject_profile", "-created_at"], name="waste_docs__subject_6e1a9c_idx"),
        ),
        migrations.AddIndex(
            model_name="yardsvozsubmiterrorlog",
            index=models.Index(fields=["acknowledged_at"], name="waste_docs__acknowl_8b2c4d_idx"),
        ),
    ]
