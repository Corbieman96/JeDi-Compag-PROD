# Generated manually for Svoz yard daily limit bypass toggle.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_appsettings_waste_docs_default_range_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="svoz_disable_yard_daily_submit_limit",
            field=models.BooleanField(
                default=False,
                verbose_name="Vypnout denní limit odeslání matice ze sběrného dvora",
                help_text="Pokud zapnuté, kontrola „už dnes odesláno ze dvora“ se nebere v úvahu (bez mazání SvozTask). "
                "Pouze pro testování / vývoj — v produkci ponechte vypnuté.",
            ),
        ),
    ]
