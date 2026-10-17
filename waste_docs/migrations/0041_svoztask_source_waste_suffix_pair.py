from django.db import migrations, models
import django.db.models.deletion


def backfill_source_pair(apps, schema_editor):
    SvozTask = apps.get_model("waste_docs", "SvozTask")
    Pair = apps.get_model("catalogs", "NameSubjectWasteSuffixPair")
    pair_map = {
        (p.subject_profile_id, p.waste_type_id, p.suffix_id): p.pk
        for p in Pair.objects.all().only("pk", "subject_profile_id", "waste_type_id", "suffix_id")
    }
    for task in SvozTask.objects.filter(source_waste_suffix_pair__isnull=True).iterator(chunk_size=500):
        pk = pair_map.get((task.subject_profile_id, task.waste_type_id, task.suffix_id))
        if pk:
            SvozTask.objects.filter(pk=task.pk).update(source_waste_suffix_pair_id=pk)


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0049_namesubjectwastesuffixpair_yard_svoz_exception_slot"),
        ("waste_docs", "0040_ridetemplate_applicable_vehicle_kinds"),
    ]

    operations = [
        migrations.AddField(
            model_name="svoztask",
            name="source_waste_suffix_pair",
            field=models.ForeignKey(
                blank=True,
                help_text="Pár odpad–koncovka z matice sběrného dvora, ze kterého úkol vznikl.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="svoz_tasks",
                to="catalogs.namesubjectwastesuffixpair",
                verbose_name="Řádek matice požadavku",
            ),
        ),
        migrations.RunPython(backfill_source_pair, migrations.RunPython.noop),
    ]
