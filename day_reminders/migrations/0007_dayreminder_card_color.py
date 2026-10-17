from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("day_reminders", "0006_dayreminder_monthly"),
    ]

    operations = [
        migrations.AddField(
            model_name="dayreminder",
            name="card_color",
            field=models.CharField(
                choices=[
                    ("yellow", "Žlutá"),
                    ("green", "Zelená"),
                    ("blue", "Modrá"),
                    ("red", "Červená"),
                    ("purple", "Fialová"),
                    ("gray", "Šedá"),
                ],
                default="yellow",
                max_length=16,
                verbose_name="Barva karty",
            ),
        ),
    ]
