from django.db import migrations, models


def setup_blank_activity(apps, schema_editor):
    ActivityCatalog = apps.get_model("catalogs", "ActivityCatalog")
    ActivityFieldRule = apps.get_model("catalogs", "ActivityFieldRule")

    activity, _ = ActivityCatalog.objects.get_or_create(
        name="Bianko průvodka",
        defaults={
            "visible_for_submitter": False,
            "require_nitropodnikovy_subjekt": False,
            "evidence_without_excel": False,
        },
    )

    rules = {
        "snd_cislo": "required",
        "zpo": "off",
        "pio": "off",
        "suffix": "optional",
        "waste_type": "optional",
        "name": "optional",
        "fulfillment_address": "optional",
        "driver": "optional",
        "vehicle_rz": "optional",
        "container_1": "optional",
        "container_2": "optional",
        "contact_phone": "optional",
        "contract_number": "optional",
        "contact_note": "optional",
    }
    for field_key, mode in rules.items():
        ActivityFieldRule.objects.update_or_create(
            activity=activity,
            field_key=field_key,
            defaults={"mode": mode},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0045_pruvodka_updated_at"),
        ("catalogs", "0049_namesubjectwastesuffixpair_yard_svoz_exception_slot"),
    ]

    operations = [
        migrations.AddField(
            model_name="pruvodka",
            name="is_blank_pruvodka",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="Nouzová prázdná průvodka se SND; údaje se doplní později nebo se archivuje nepoužitá.",
                verbose_name="Bianko průvodka",
            ),
        ),
        migrations.RunPython(setup_blank_activity, migrations.RunPython.noop),
    ]
