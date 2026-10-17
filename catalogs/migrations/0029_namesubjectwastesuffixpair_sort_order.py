from django.db import migrations, models


def backfill_sort_order(apps, schema_editor):
    Pair = apps.get_model("catalogs", "NameSubjectWasteSuffixPair")
    for sid in Pair.objects.values_list("subject_profile_id", flat=True).distinct():
        pairs = list(Pair.objects.filter(subject_profile_id=sid).order_by("id"))
        for idx, p in enumerate(pairs):
            Pair.objects.filter(pk=p.pk).update(sort_order=idx)


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0028_namesubjectwastesuffixpair_yard_svoz_activity"),
    ]

    operations = [
        migrations.AddField(
            model_name="namesubjectwastesuffixpair",
            name="sort_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="Pořadí v tabulce a v matici požadavku na svoz (přetahováním řádků v úpravě subjektu).",
                verbose_name="Pořadí řádků",
            ),
        ),
        migrations.AlterModelOptions(
            name="namesubjectwastesuffixpair",
            options={
                "ordering": ["sort_order", "id"],
                "verbose_name": "Pár odpad–koncovka u subjektu",
                "verbose_name_plural": "Páry odpad–koncovka u subjektu",
            },
        ),
        migrations.RunPython(backfill_sort_order, migrations.RunPython.noop),
    ]
