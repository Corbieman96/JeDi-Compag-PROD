from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("day_reminders", "0003_dayreminder_title"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DayReminderCompletion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("resolved_on", models.DateField(db_index=True, verbose_name="Vyřešeno pro den")),
                ("resolved_at", models.DateTimeField(auto_now_add=True, verbose_name="Čas označení")),
                (
                    "reminder",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="completions",
                        to="day_reminders.dayreminder",
                    ),
                ),
                (
                    "resolved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="day_reminder_completions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("reminder", "resolved_on"),
                        name="unique_dayreminder_completion_per_day",
                    ),
                ],
            },
        ),
    ]
