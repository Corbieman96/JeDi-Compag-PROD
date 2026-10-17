from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_appsettings_svoz_disable_yard_daily_submit_limit"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="enforce_container_passport_move_check",
            field=models.BooleanField(
                default=True,
                verbose_name="Kontrolovat přistavení/stažení kontejneru podle pasportu",
                help_text="Pokud zapnuté, stejné číslo kontejneru nelze použít na více otevřených jízdách současně. "
                "Vypnutí povolí souběh i při shodném pasportu.",
            ),
        ),
    ]
