# Generated manually for PIO fields on subject profile

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalogs", "0039_activitycatalog_follow_up_activities"),
    ]

    operations = [
        migrations.AddField(
            model_name="namesubjectprofile",
            name="pio_officer_name",
            field=models.CharField(blank=True, max_length=255, verbose_name="PIO — jméno odpovědné osoby"),
        ),
        migrations.AddField(
            model_name="namesubjectprofile",
            name="pio_officer_phone",
            field=models.CharField(blank=True, max_length=20, verbose_name="PIO — telefon osoby"),
        ),
        migrations.AddField(
            model_name="namesubjectprofile",
            name="pio_officer_email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="PIO — e-mail"),
        ),
        migrations.AddField(
            model_name="namesubjectprofile",
            name="pio_waste_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pio_subject_profiles",
                to="catalogs.wastetypecatalog",
                verbose_name="PIO — vybraný druh odpadu",
            ),
        ),
        migrations.AddField(
            model_name="namesubjectprofile",
            name="pio_suffix",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pio_subject_profiles",
                to="catalogs.suffixcatalog",
                verbose_name="PIO — vybraná koncovka",
            ),
        ),
        migrations.AddField(
            model_name="namesubjectprofile",
            name="pio_outside_map_lat",
            field=models.DecimalField(
                blank=True, decimal_places=7, max_digits=10, null=True, verbose_name="PIO — mimo provozovnu (lat)"
            ),
        ),
        migrations.AddField(
            model_name="namesubjectprofile",
            name="pio_outside_map_lng",
            field=models.DecimalField(
                blank=True, decimal_places=7, max_digits=10, null=True, verbose_name="PIO — mimo provozovnu (lng)"
            ),
        ),
        migrations.AddField(
            model_name="namesubjectprofile",
            name="pio_outside_map_orp",
            field=models.CharField(
                blank=True, max_length=120, verbose_name="PIO — ORP z mapy (placeholder iczujfirmy)"
            ),
        ),
        migrations.AddField(
            model_name="namesubjectprofile",
            name="pio_outside_map_iczuj",
            field=models.CharField(blank=True, max_length=20, verbose_name="PIO — IČZÚJ z mapy (placeholder orp)"),
        ),
    ]
