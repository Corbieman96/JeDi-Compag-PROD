from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0054_pruvodka_source_waste_suffix_pair"),
    ]

    operations = [
        migrations.AddField(
            model_name="pruvodka",
            name="weight_kg",
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                max_digits=10,
                null=True,
                verbose_name="Hmotnost (kg)",
            ),
        ),
        migrations.AddField(
            model_name="pruvodka",
            name="weight_snapshot",
            field=models.CharField(
                blank=True,
                max_length=32,
                verbose_name="Hmotnost — snapshot pro Excel",
            ),
        ),
    ]
