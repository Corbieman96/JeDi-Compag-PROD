from django.db import migrations, models


def copy_fk_to_m2m(apps, schema_editor):
    Pair = apps.get_model("catalogs", "NameSubjectWasteSuffixPair")
    for pair in Pair.objects.exclude(yard_vehicle_kind_id__isnull=True).iterator():
        pair.yard_vehicle_kinds.add(pair.yard_vehicle_kind_id)


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0047_vehiclekindcatalog_compatibility"),
    ]

    operations = [
        migrations.AddField(
            model_name="namesubjectwastesuffixpair",
            name="yard_vehicle_kinds",
            field=models.ManyToManyField(
                blank=True,
                related_name="yard_waste_suffix_pairs_multi",
                to="catalogs.vehiclekindcatalog",
                verbose_name="Druhy vozidla pro svoz",
            ),
        ),
        migrations.AlterField(
            model_name="namesubjectwastesuffixpair",
            name="yard_vehicle_kind",
            field=models.ForeignKey(
                blank=True,
                help_text="Synchronizuje se z prvního vybraného druhu v seznamu níže; pro plán a úkoly.",
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name="yard_waste_suffix_pairs",
                to="catalogs.vehiclekindcatalog",
                verbose_name="Druh vozidla pro svoz (hlavní)",
            ),
        ),
        migrations.RunPython(copy_fk_to_m2m, migrations.RunPython.noop),
    ]
