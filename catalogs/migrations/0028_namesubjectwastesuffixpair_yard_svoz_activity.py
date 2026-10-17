import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0027_namesubjectwastesuffixpair_yard_svoz_display_label"),
    ]

    operations = [
        migrations.AddField(
            model_name="namesubjectwastesuffixpair",
            name="yard_svoz_activity",
            field=models.ForeignKey(
                blank=True,
                help_text="Povinné u zapnutého svozu — jaká činnost se u kontejneru provádí (předvyplní se v průvodce).",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="yard_svoz_waste_suffix_pairs",
                to="catalogs.activitycatalog",
                verbose_name="Činnost (svoz z dvora)",
            ),
        ),
    ]
