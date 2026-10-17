from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0061_yardsvozsubmiterrorlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="yardsvozsubmiterrorlog",
            name="source",
            field=models.CharField(
                choices=[("submit", "Odeslání"), ("live", "Živá kontrola")],
                db_index=True,
                default="submit",
                max_length=16,
                verbose_name="Zdroj",
            ),
        ),
        migrations.AddField(
            model_name="yardsvozsubmissionlog",
            name="result_summary",
            field=models.CharField(
                blank=True,
                help_text="Řidič / požadavek bez řidiče / nebezpečný odpad.",
                max_length=300,
                verbose_name="Výsledek odeslání",
            ),
        ),
    ]
