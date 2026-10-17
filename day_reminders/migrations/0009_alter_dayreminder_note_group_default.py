from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("day_reminders", "0008_dayreminder_note_group"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dayreminder",
            name="note_group",
            field=models.CharField(
                choices=[("request", "Požadavek"), ("other", "Ostatní")],
                db_index=True,
                default="request",
                help_text="Rozlišení pro tisk: Požadavek vs Ostatní.",
                max_length=16,
                verbose_name="Druh poznámky",
            ),
        ),
    ]
