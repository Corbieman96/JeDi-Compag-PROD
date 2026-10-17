import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0050_pruvodka_soft_delete_log"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RideEmailRecipient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254, unique=True, verbose_name="E-mail příjemce")),
                ("label", models.CharField(blank=True, max_length=120, verbose_name="Popisek")),
                ("last_used_at", models.DateTimeField(blank=True, null=True, verbose_name="Naposledy použito")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ride_email_recipients_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Vytvořil",
                    ),
                ),
            ],
            options={
                "verbose_name": "Uložený příjemce e-mailu jízdy",
                "verbose_name_plural": "Uložení příjemci e-mailu jízdy",
                "ordering": ("-last_used_at", "email"),
            },
        ),
    ]
