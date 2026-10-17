# Generated manually for VOK import (objem m³)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0045_pasport_stredisko_and_passport_vok_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="containerpassport",
            name="volume_m3",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                verbose_name="Objem (m³)",
                help_text="Z importu VOK (sloupec m³) nebo ručně.",
            ),
        ),
    ]
