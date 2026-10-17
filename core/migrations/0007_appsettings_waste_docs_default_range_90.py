from django.db import migrations, models


def set_default_range_90(apps, schema_editor):
    AppSettings = apps.get_model("core", "AppSettings")
    AppSettings.objects.filter(pk=1, waste_docs_default_range_days=14).update(
        waste_docs_default_range_days=90
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_appsettings_enforce_container_passport_move_check"),
    ]

    operations = [
        migrations.AlterField(
            model_name="appsettings",
            name="waste_docs_default_range_days",
            field=models.PositiveSmallIntegerField(
                default=90,
                help_text="Počet dnů zpět pro předvyplnění filtru Od/Do na /waste-docs/.",
                verbose_name="Výchozí rozsah dnů pro seznam jízd",
            ),
        ),
        migrations.RunPython(set_default_range_90, migrations.RunPython.noop),
    ]
