from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0047_ride_group_email_dispatch"),
    ]

    operations = [
        migrations.AddField(
            model_name="pruvodka",
            name="ride_route_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="0 = výchozí (podle ride_sequence). Nastavuje se ručním seřazením na dashboardu.",
                verbose_name="Pořadí v trase jízdy",
            ),
        ),
    ]
