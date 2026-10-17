from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0059_svoztask_auto_pruvodka_last_error"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="pruvodka",
            name="waste_docs_pruvodka_uniq_drive_date_snd_nonempty",
        ),
        migrations.AddConstraint(
            model_name="pruvodka",
            constraint=models.UniqueConstraint(
                condition=models.Q(("snd_cislo_listu__gt", ""))
                & models.Q(("is_archived", False)),
                fields=("drive_date", "snd_cislo_listu"),
                name="waste_docs_pruvodka_uniq_drive_date_snd_nonempty",
            ),
        ),
    ]
