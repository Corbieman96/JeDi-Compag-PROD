# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_appsettings_waste_docs_default_range_90"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="role_permission_defaults",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Pro každou roli lze nastavit výchozí oprávnění (např. generování PIO). "
                "Uživatel s přepínačem „Dědit z role“ v /users/…/edit/ použije hodnotu odtud.",
                verbose_name="Oprávnění — výchozí podle rolí",
            ),
        ),
    ]
