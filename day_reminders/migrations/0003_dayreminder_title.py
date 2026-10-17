from django.db import migrations, models


def forwards_title_from_text(apps, schema_editor):
    DayReminder = apps.get_model("day_reminders", "DayReminder")
    for r in DayReminder.objects.all():
        body = (r.text or "").strip()
        r.title = (body[:160] if body else "Poznámka")
        r.save(update_fields=["title"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("day_reminders", "0002_repeat_weekdays"),
    ]

    operations = [
        migrations.AddField(
            model_name="dayreminder",
            name="title",
            field=models.CharField(default="", max_length=160, verbose_name="Název"),
        ),
        migrations.RunPython(forwards_title_from_text, noop_reverse),
        migrations.AlterField(
            model_name="dayreminder",
            name="title",
            field=models.CharField(max_length=160, verbose_name="Název"),
        ),
        migrations.AlterField(
            model_name="dayreminder",
            name="text",
            field=models.TextField(blank=True, verbose_name="Text"),
        ),
    ]
