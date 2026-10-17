from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_appsettings_session_idle_timeout"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="no_service_on_saturday",
            field=models.BooleanField(
                default=True,
                help_text="Nové požadavky a úkoly ze sběrného dvora se ze soboty posunou na další provozní den.",
                verbose_name="Sobota — nejezdíme",
            ),
        ),
        migrations.AddField(
            model_name="appsettings",
            name="no_service_on_sunday",
            field=models.BooleanField(
                default=True,
                help_text="Nové požadavky a úkoly ze sběrného dvora se z neděle posunou na další provozní den.",
                verbose_name="Neděle — nejezdíme",
            ),
        ),
    ]
