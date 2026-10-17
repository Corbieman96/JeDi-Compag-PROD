# Generated manually — zkopíruje existující pio_document na pár do první revize.

from django.db import migrations


def migrate_legacy_pio_documents(apps, schema_editor):
    Pair = apps.get_model("catalogs", "namesubjectwastesuffixpair")
    PioRevision = apps.get_model("pio", "piorevision")
    db_alias = schema_editor.connection.alias

    for p in Pair.objects.using(db_alias).only("pk", "pio_document").iterator():
        raw = getattr(p, "pio_document", "") or ""
        if isinstance(raw, str):
            path = raw.strip()
        else:
            path = (getattr(raw, "name", None) or str(raw)).strip()
        if not path:
            continue
        if PioRevision.objects.using(db_alias).filter(pair_id=p.pk).exists():
            continue
        rev = PioRevision(
            pair_id=p.pk,
            note="Import z pole pio_document (před archivy PIO)",
        )
        rev.file.name = path
        rev.save(using=db_alias)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("pio", "0002_file_extensions"),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_pio_documents, noop),
    ]
