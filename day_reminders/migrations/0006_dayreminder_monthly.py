from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("day_reminders", "0005_dayreminder_source_svoz_task"),
    ]

    operations = [
        migrations.AddField(
            model_name="dayreminder",
            name="repeat_monthly",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='{"ordinal": 1, "weekday": 2} — např. každá 1. středa; ordinal -1 = poslední výskyt.',
                verbose_name="Měsíční pravidlo",
            ),
        ),
        migrations.AlterField(
            model_name="dayreminder",
            name="kind",
            field=models.CharField(
                choices=[
                    ("one_off", "Jednorázová"),
                    ("weekly", "Týdně"),
                    ("monthly", "Měsíčně"),
                    ("rolling", "Přenášet do vyřešení"),
                ],
                db_index=True,
                max_length=16,
            ),
        ),
    ]
