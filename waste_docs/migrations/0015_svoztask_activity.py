import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0028_namesubjectwastesuffixpair_yard_svoz_activity"),
        ("waste_docs", "0014_svoztask_matrix_display_label"),
    ]

    operations = [
        migrations.AddField(
            model_name="svoztask",
            name="activity",
            field=models.ForeignKey(
                blank=True,
                help_text="Z řádku matice v číselníku; předvyplnění průvodky.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="svoz_tasks",
                to="catalogs.activitycatalog",
                verbose_name="Činnost",
            ),
        ),
    ]
