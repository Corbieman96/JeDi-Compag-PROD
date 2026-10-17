from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0055_pruvodka_weight_kg"),
    ]

    operations = [
        migrations.RenameField(
            model_name="pruvodka",
            old_name="weight_kg",
            new_name="weight_t",
        ),
        migrations.AlterField(
            model_name="pruvodka",
            name="weight_t",
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                max_digits=10,
                null=True,
                verbose_name="Hmotnost (t)",
            ),
        ),
    ]
