from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="OfflineAddress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("city", models.CharField(blank=True, max_length=120)),
                ("street", models.CharField(blank=True, max_length=160)),
                ("house_number", models.CharField(blank=True, max_length=32)),
                ("postal_code", models.CharField(blank=True, max_length=16)),
                ("label", models.CharField(max_length=255)),
                ("lat", models.DecimalField(decimal_places=7, max_digits=10)),
                ("lng", models.DecimalField(decimal_places=7, max_digits=10)),
                ("city_norm", models.CharField(db_index=True, max_length=120)),
                ("street_norm", models.CharField(db_index=True, max_length=160)),
                ("label_norm", models.CharField(db_index=True, max_length=255)),
            ],
            options={
                "ordering": ("label",),
            },
        ),
        migrations.AddIndex(
            model_name="offlineaddress",
            index=models.Index(fields=["city_norm", "street_norm"], name="addr_city_street_idx"),
        ),
        migrations.AddIndex(
            model_name="offlineaddress",
            index=models.Index(fields=["label_norm"], name="addr_label_idx"),
        ),
    ]
