from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0062_error_log_source_and_submission_result"),
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
                ],
                db_index=True,
                default="submit",
                max_length=16,
                verbose_name="Zdroj",
            ),
        ),
    ]
