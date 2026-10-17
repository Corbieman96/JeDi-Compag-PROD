from django.db import migrations


TABLE = "catalogs_namesubjectwastesuffixpair"
COLUMN = "ride_note"


def _column_names(schema_editor, table: str) -> set[str]:
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table)
    return {col.name for col in description}


def ensure_ride_note_column(apps, schema_editor):
    if COLUMN in _column_names(schema_editor, TABLE):
        return
    schema_editor.execute(
        f'ALTER TABLE {TABLE} ADD COLUMN {COLUMN} varchar(200) DEFAULT \'\' NOT NULL'
    )


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    """Doplní ride_note do DB tam, kde 0060 jen obnovilo stav modelu."""

    dependencies = [
        ("catalogs", "0060_namesubjectwastesuffixpair_ride_note"),
    ]

    operations = [
        migrations.RunPython(ensure_ride_note_column, noop_reverse),
    ]
