# Generated manually

from django.db import migrations, models


def forwards_copy_vehicle_kind_to_m2m(apps, schema_editor):
    RideTemplate = apps.get_model("waste_docs", "RideTemplate")
    for rt in RideTemplate.objects.exclude(vehicle_kind_id__isnull=True).iterator():
        rt.applicable_vehicle_kinds.add(rt.vehicle_kind_id)


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0039_driver_portal_link_and_completed_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="ridetemplate",
            name="applicable_vehicle_kinds",
            field=models.ManyToManyField(
                blank=True,
                related_name="ride_templates_applicable",
                to="catalogs.vehiclekindcatalog",
                verbose_name="Platí pro druhy vozidel",
            ),
        ),
        migrations.RunPython(forwards_copy_vehicle_kind_to_m2m, backwards_noop),
    ]
