# Generated manually for note_group

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("day_reminders", "0007_dayreminder_card_color"),
    ]

    operations = [
        migrations.AddField(
            model_name="dayreminder",
            name="note_group",
            field=models.CharField(
                choices=[("request", "Požadavek"), ("other", "Ostatní")],
                db_index=True,
                default="other",
                help_text="Rozlišení pro tisk: Požadavek vs Ostatní.",
                max_length=16,
                verbose_name="Druh poznámky",
            ),
        ),
    ]
