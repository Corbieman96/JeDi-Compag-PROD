from django.db import migrations, models
import django.db.models.deletion


def backfill_pruvodka_source_pairs(apps, schema_editor):
    from catalogs.services.name_subject_pair_vehicle_kinds import pair_for_pruvodka_context

    NameSubjectProfile = apps.get_model("catalogs", "NameSubjectProfile")
    Pruvodka = apps.get_model("waste_docs", "Pruvodka")

    for ride in (
        Pruvodka.objects.filter(
            source_waste_suffix_pair_id__isnull=True,
            name_id__isnull=False,
            waste_type_id__isnull=False,
            suffix_id__isnull=False,
        )
        .select_related("vehicle_rz", "container_passport")
        .iterator(chunk_size=200)
    ):
        profile = NameSubjectProfile.objects.filter(name_id=ride.name_id).first()
        if not profile:
            continue
        pair = pair_for_pruvodka_context(
            subject_profile=profile,
            waste_type_id=ride.waste_type_id,
            suffix_id=ride.suffix_id,
            vehicle_rz=ride.vehicle_rz,
            container_passport=ride.container_passport,
        )
        if pair:
            Pruvodka.objects.filter(pk=ride.pk).update(source_waste_suffix_pair_id=pair.pk)


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0049_namesubjectwastesuffixpair_yard_svoz_exception_slot"),
        ("waste_docs", "0053_svoz_matrix_queue_submitted_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="pruvodka",
            name="source_waste_suffix_pair",
            field=models.ForeignKey(
                blank=True,
                help_text="Konkrétní řádek z „Povolené odpady a koncovky“ u subjektu pro tuto jízdu.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pruvodky",
                to="catalogs.namesubjectwastesuffixpair",
                verbose_name="Řádek matice (odpad–koncovka)",
            ),
        ),
        migrations.RunPython(backfill_pruvodka_source_pairs, migrations.RunPython.noop),
    ]
