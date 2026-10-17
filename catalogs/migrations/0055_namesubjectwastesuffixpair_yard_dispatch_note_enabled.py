from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0054_namesubjectwastesuffixpair_yard_dispatch_notes"),
    ]

    operations = [
        migrations.AddField(
            model_name="namesubjectwastesuffixpair",
            name="yard_dispatch_note_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Po hlaseni ze sberneho dvora u tohoto radku matice vytvorit jednorazovou poznamku v panelu dispecera.",
                verbose_name="Poznamka pro dispecera",
            ),
        ),
    ]
