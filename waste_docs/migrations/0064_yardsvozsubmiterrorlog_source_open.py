# Generated manually for YardSvozSubmitErrorLog.source open

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0063_yardsvozsubmiterrorlog_source_login"),
    ]

    operations = [
        migrations.AlterField(
            model_name="yardsvozsubmiterrorlog",
            name="source",
            field=models.CharField(
                choices=[
                    ("submit", "Odeslání"),
                    ("live", "Živá kontrola"),
                    ("login", "Přihlášení"),
                    ("open", "Otevření matice"),
                ],
                db_index=True,
                default="submit",
                max_length=16,
                verbose_name="Zdroj",
            ),
        ),
    ]
