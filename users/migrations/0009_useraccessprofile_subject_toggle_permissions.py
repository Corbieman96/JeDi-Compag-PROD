from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_useraccessprofile_nav_invoice_queue"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccessprofile",
            name="can_toggle_subject_collection_yard",
            field=models.BooleanField(default=False, verbose_name="Smí měnit: Lokalita sběrného dvora"),
        ),
        migrations.AddField(
            model_name="useraccessprofile",
            name="can_toggle_subject_dispatch_group",
            field=models.BooleanField(default=False, verbose_name="Smí měnit: Skupina v plánu svozů"),
        ),
        migrations.AddField(
            model_name="useraccessprofile",
            name="can_toggle_subject_is_municipality",
            field=models.BooleanField(default=False, verbose_name="Smí měnit: Jedná se o obec"),
        ),
        migrations.AddField(
            model_name="useraccessprofile",
            name="can_toggle_subject_nitropodnikovy",
            field=models.BooleanField(default=False, verbose_name="Smí měnit: Nitropodnikový subjekt"),
        ),
        migrations.AddField(
            model_name="useraccessprofile",
            name="can_toggle_subject_system_generates_zpo",
            field=models.BooleanField(default=True, verbose_name="Smí měnit: Generovat systémové ZPO k jízdám"),
        ),
        migrations.AddField(
            model_name="useraccessprofile",
            name="can_toggle_subject_yard_allow_matrix",
            field=models.BooleanField(default=False, verbose_name="Smí měnit: Povolit matici požadavků"),
        ),
        migrations.AddField(
            model_name="useraccessprofile",
            name="can_toggle_subject_yard_allow_pruvodka",
            field=models.BooleanField(default=False, verbose_name="Smí měnit: Povolit průvodku z dvora"),
        ),
    ]
