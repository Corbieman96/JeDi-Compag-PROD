from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("waste_docs", "0015_svoztask_activity"),
    ]

    operations = [
        migrations.AddField(
            model_name="svoztask",
            name="yard_contact_note",
            field=models.CharField(
                blank=True,
                help_text="Z matice požadavku; při založení průvodky se přenese do pole Poznámka.",
                max_length=200,
                verbose_name="Poznámka ze dvora",
            ),
        ),
    ]
