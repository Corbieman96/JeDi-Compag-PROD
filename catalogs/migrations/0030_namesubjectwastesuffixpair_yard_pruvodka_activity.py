import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0029_namesubjectwastesuffixpair_sort_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="namesubjectwastesuffixpair",
            name="yard_pruvodka_activity",
            field=models.ForeignKey(
                blank=True,
                help_text="Při zapnuté průvodce z dvora — jaká činnost se v průvodce použije. Pokud prázdné, použije se „Činnost (svoz)“, pokud je vyplněná.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="yard_pruvodka_waste_suffix_pairs",
                to="catalogs.activitycatalog",
                verbose_name="Činnost (průvodka z dvora)",
            ),
        ),
    ]
