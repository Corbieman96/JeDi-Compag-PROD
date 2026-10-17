from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0058_printfilemark_is_current"),
    ]

    operations = [
        migrations.AddField(
            model_name="svoztask",
            name="auto_pruvodka_last_error",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Důvod, proč se po přiřazení řidiče nezaložila průvodka automaticky.",
                max_length=500,
                verbose_name="Poslední chyba auto-jízdy",
            ),
        ),
        migrations.AddField(
            model_name="svoztask",
            name="auto_pruvodka_last_error_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Čas poslední chyby auto-jízdy",
            ),
        ),
    ]
