from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0026_yard_svoz_and_vehicle_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="namesubjectwastesuffixpair",
            name="yard_svoz_display_label",
            field=models.CharField(
                blank=True,
                help_text="Vlastní text pro sběrný dvůr u řádku se zapnutým svozem; prázdné = zobrazit druh odpadu z číselníku. "
                "Ukládají se stále druh odpadu, koncovka, druh vozidla a kontejnery.",
                max_length=200,
                verbose_name="Název v matici požadavku",
            ),
        ),
    ]
