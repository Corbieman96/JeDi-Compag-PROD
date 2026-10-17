from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0013_yard_svoz_and_vehicle_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="svoztask",
            name="matrix_display_label",
            field=models.CharField(
                blank=True,
                help_text="Kopie volitelného názvu z číselníku v době zařazení do fronty; nepřebírá roli koncovky ani druhu odpadu.",
                max_length=200,
                verbose_name="Název řádku (zobrazení)",
            ),
        ),
    ]
