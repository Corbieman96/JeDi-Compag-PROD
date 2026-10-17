from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0053_activitycatalog_follow_up_terminal_activities"),
    ]

    operations = [
        migrations.AddField(
            model_name="namesubjectwastesuffixpair",
            name="yard_dispatch_note_title",
            field=models.CharField(
                blank=True,
                help_text="Po odeslani hlaseni ze sberneho dvora se zobrazi dispecerovi v panelu Posledni ukoly / poznamky.",
                max_length=160,
                verbose_name="Nazev poznamky (dispecer)",
            ),
        ),
        migrations.AddField(
            model_name="namesubjectwastesuffixpair",
            name="yard_dispatch_note_text",
            field=models.TextField(
                blank=True,
                help_text="Volitelna sablona textu pro dispecera; po odeslani hlaseni se doplni o subjekt, kontejnery a poznamku z matice.",
                verbose_name="Text poznamky (dispecer)",
            ),
        ),
    ]
