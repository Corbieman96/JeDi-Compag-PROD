from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0049_yard_hazardous_waste_request"),
        ("day_reminders", "0004_dayremindercompletion"),
    ]

    operations = [
        migrations.AddField(
            model_name="dayreminder",
            name="source_svoz_task",
            field=models.ForeignKey(
                blank=True,
                help_text="Poznámka vytvořená automaticky po odeslání matice ze sběrného dvora.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="yard_dispatch_notes",
                to="waste_docs.svoztask",
                verbose_name="Zdroj — hlášení ze sběrného dvora",
            ),
        ),
    ]
