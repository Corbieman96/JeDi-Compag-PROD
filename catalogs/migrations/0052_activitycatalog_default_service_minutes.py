from django.db import migrations, models


def _set_default_service_minutes(apps, schema_editor):
    ActivityCatalog = apps.get_model("catalogs", "ActivityCatalog")
    rules = (
        (("výměna", "vymena"), 35),
        (("svoz",), 20),
        (("přistaven", "pristaven"), 12),
        (("stažení", "stazeni", "stáhnout", "stahnout"), 18),
        (("odvoz",), 20),
    )
    for activity in ActivityCatalog.objects.all():
        if activity.default_service_minutes is not None:
            continue
        name_lower = (activity.name or "").strip().lower()
        for patterns, minutes in rules:
            if any(p in name_lower for p in patterns):
                activity.default_service_minutes = minutes
                activity.save(update_fields=["default_service_minutes"])
                break


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0051_subjectyardsettings_ratio_min_containers"),
    ]

    operations = [
        migrations.AddField(
            model_name="activitycatalog",
            name="default_service_minutes",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Odhad času auta na místě pro AI prompt řazení trasy; lze doladit ručně.",
                null=True,
                verbose_name="Výchozí délka zastávky (min)",
            ),
        ),
        migrations.RunPython(_set_default_service_minutes, migrations.RunPython.noop),
    ]
