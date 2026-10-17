from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0052_activitycatalog_default_service_minutes"),
    ]

    operations = [
        migrations.AddField(
            model_name="activitycatalog",
            name="follow_up_terminal_activities",
            field=models.ManyToManyField(
                blank=True,
                help_text="Které z navazujících činností případ definitivně uzavřou (např. Stažení). Ostatní jen evidují mezikrok (Výměna).",
                related_name="terminal_for_preceding",
                to="catalogs.activitycatalog",
                verbose_name="Uzavírají návaznost",
            ),
        ),
    ]
