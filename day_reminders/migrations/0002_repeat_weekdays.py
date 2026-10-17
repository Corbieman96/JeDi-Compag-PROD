# Generated manually: více dnů v týdnu místo jednoho repeat_weekday

from django.db import migrations, models


def forwards_copy_weekday(apps, schema_editor):
    DayReminder = apps.get_model("day_reminders", "DayReminder")
    for r in DayReminder.objects.all():
        if r.kind == "weekly":
            wd = r.repeat_weekday
            r.repeat_weekdays = [int(wd)] if wd is not None else []
        else:
            r.repeat_weekdays = []
        r.save(update_fields=["repeat_weekdays"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("day_reminders", "0001_initial"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="dayreminder",
            name="day_reminde_kind_b93f20_idx",
        ),
        migrations.AddField(
            model_name="dayreminder",
            name="repeat_weekdays",
            field=models.JSONField(blank=True, default=list, null=True, verbose_name="Dny v týdnu (0=Po … 6=Ne)"),
        ),
        migrations.RunPython(forwards_copy_weekday, noop_reverse),
        migrations.RemoveField(
            model_name="dayreminder",
            name="repeat_weekday",
        ),
        migrations.AlterField(
            model_name="dayreminder",
            name="repeat_weekdays",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="U týdenní připomínky seznam čísel 0–6, např. [0,2,4] pro Po, St, Pá.",
                verbose_name="Dny v týdnu (0=Po … 6=Ne)",
            ),
        ),
    ]
