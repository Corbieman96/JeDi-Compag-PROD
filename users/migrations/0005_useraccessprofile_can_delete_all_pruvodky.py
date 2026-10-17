from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_useraccessprofile_nav_dashboard_pruvodky"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccessprofile",
            name="can_delete_all_pruvodky",
            field=models.BooleanField(
                default=False,
                help_text="Pouze pro admina; povolí hromadné smazání všech průvodek na stránce /waste-docs/.",
                verbose_name="Smí smazat všechny průvodky",
            ),
        ),
    ]
