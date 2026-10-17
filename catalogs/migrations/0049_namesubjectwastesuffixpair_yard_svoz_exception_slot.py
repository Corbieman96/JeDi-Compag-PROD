from collections import defaultdict

from django.db import migrations, models


def backfill_exception_slots(apps, schema_editor):
    Pair = apps.get_model("catalogs", "NameSubjectWasteSuffixPair")
    groups: dict[tuple[int, int], list] = defaultdict(list)
    for pair in Pair.objects.filter(
        yard_svoz_enabled=True,
        yard_svoz_auto_assign_driver=False,
        yard_vehicle_kind_id__isnull=False,
    ).order_by("subject_profile_id", "yard_vehicle_kind_id", "sort_order", "id"):
        groups[(pair.subject_profile_id, pair.yard_vehicle_kind_id)].append(pair)
    for pairs in groups.values():
        for idx, pair in enumerate(pairs[:4]):
            if pair.yard_svoz_exception_slot is None:
                pair.yard_svoz_exception_slot = idx + 1
                pair.save(update_fields=["yard_svoz_exception_slot"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0048_namesubjectwastesuffixpair_yard_vehicle_kinds"),
    ]

    operations = [
        migrations.AddField(
            model_name="namesubjectwastesuffixpair",
            name="yard_svoz_exception_slot",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Povinné u výjimky (vypnutý běžný svoz): který sloupec V1–V4 v Plánu svozů obsluhuje kontejnery z tohoto řádku matice. Unikátní pro dvůr a hlavní druh vozidla řádku.",
                null=True,
                verbose_name="Výjimka — slot plánu (V1–V4)",
            ),
        ),
        migrations.RunPython(backfill_exception_slots, migrations.RunPython.noop),
    ]
