from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0050_pruvodka_updated_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="subjectyardsettings",
            name="yard_svoz_ratio_min_containers",
            field=models.PositiveSmallIntegerField(
                default=5,
                help_text=(
                    "Při menším počtu otevřených požadavků běžného svozu na daný den se úkoly "
                    "přiřadí jen prvnímu řidiči (B1). Každý sběrný dvůr může mít jinou hodnotu."
                ),
                verbose_name="Min. požadavků pro poměr řidičů",
            ),
        ),
    ]
