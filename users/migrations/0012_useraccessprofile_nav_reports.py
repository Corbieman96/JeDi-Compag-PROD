# Generated manually for nav_reports

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0011_can_export_name_subject_pio_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccessprofile",
            name="nav_reports",
            field=models.CharField(
                choices=[("inherit", "Dědit z role"), ("show", "Vždy zobrazit"), ("hide", "Skrýt")],
                default="inherit",
                max_length=16,
                verbose_name="Menu: Reporty",
            ),
        ),
    ]
