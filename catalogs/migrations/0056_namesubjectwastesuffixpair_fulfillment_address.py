from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0055_namesubjectwastesuffixpair_yard_dispatch_note_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="namesubjectwastesuffixpair",
            name="fulfillment_address",
            field=models.ForeignKey(
                blank=True,
                help_text="Prázdné = použije se centrální adresa plnění subjektu.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pair_fulfillment_rows",
                to="catalogs.addresscatalog",
                verbose_name="Adresa plnění (volitelná)",
            ),
        ),
    ]
