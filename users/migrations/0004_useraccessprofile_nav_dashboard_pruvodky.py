from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_svoz_task_and_sberny_subject"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccessprofile",
            name="nav_dashboard",
            field=models.CharField(
                choices=[
                    ("inherit", "Dědit z role"),
                    ("show", "Vždy zobrazit"),
                    ("hide", "Skrýt"),
                ],
                default="inherit",
                max_length=16,
                verbose_name="Menu: Dashboard",
            ),
        ),
        migrations.AddField(
            model_name="useraccessprofile",
            name="nav_pruvodky",
            field=models.CharField(
                choices=[
                    ("inherit", "Dědit z role"),
                    ("show", "Vždy zobrazit"),
                    ("hide", "Skrýt"),
                ],
                default="inherit",
                max_length=16,
                verbose_name="Menu: Průvodky",
            ),
        ),
    ]
