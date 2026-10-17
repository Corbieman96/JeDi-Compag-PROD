from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalogs", "0043_zpo_library"),
    ]

    operations = [
        migrations.AddField(
            model_name="activitycatalog",
            name="follow_up_symbol_parent",
            field=models.CharField(
                blank=True,
                help_text="Ve sloupci Návaznost u průvodky navázané na předchozí záznam (např. ⇄ nebo ↕). Prázdné = výchozí šipka nahoru.",
                max_length=8,
                verbose_name="Symbol návaznosti k předchozí jízdě",
            ),
        ),
        migrations.AddField(
            model_name="activitycatalog",
            name="follow_up_symbol_child",
            field=models.CharField(
                blank=True,
                help_text="U průvodky, na kterou už něco navazuje — před čísly navazujících záznamů (např. ⇅). Prázdné = výchozí šipka dolů.",
                max_length=8,
                verbose_name="Symbol k navazujícím jízdám",
            ),
        ),
    ]
