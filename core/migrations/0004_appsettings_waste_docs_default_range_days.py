from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_role_nav_defaults"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="waste_docs_default_range_days",
            field=models.PositiveSmallIntegerField(
                default=14,
                help_text="Počet dnů zpět pro předvyplnění filtru Od/Do na /waste-docs/.",
                verbose_name="Výchozí rozsah dnů pro seznam jízd",
            ),
        ),
    ]
