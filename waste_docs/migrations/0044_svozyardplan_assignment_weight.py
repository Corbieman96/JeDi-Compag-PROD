from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0043_print_file_mark"),
    ]

    operations = [
        migrations.AddField(
            model_name="svozyarddriverplan",
            name="assignment_weight",
            field=models.PositiveSmallIntegerField(
                default=1,
                verbose_name="Podíl svozů",
                help_text="Váha slotu při rozdělování úkolů (např. 1 vs 3 pro poměr 1:3).",
            ),
        ),
    ]
