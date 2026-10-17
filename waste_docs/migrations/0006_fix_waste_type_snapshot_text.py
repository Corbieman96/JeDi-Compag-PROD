from django.db import migrations


def forwards(apps, schema_editor):
    Pruvodka = apps.get_model("waste_docs", "Pruvodka")
    for item in Pruvodka.objects.select_related("waste_type").all():
        if item.waste_type_id:
            item.waste_type_snapshot = item.waste_type.value or ""
            item.save(update_fields=["waste_type_snapshot"])


def backwards(apps, schema_editor):
    # Nevracíme zpět na kód; text je cílový správný stav.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0005_ride_numbering_and_drive_date"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

