from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customer_requests", "0008_customer_request_vehicle_kind_closure"),
    ]

    operations = [
        migrations.CreateModel(
            name="NoServiceCalendarDay",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("closed_date", models.DateField(db_index=True, unique=True, verbose_name="Den bez svozu")),
                (
                    "redirect_date",
                    models.DateField(
                        blank=True,
                        help_text="Prázdné = první následující provozní den.",
                        null=True,
                        verbose_name="Přesunout na",
                    ),
                ),
                ("note", models.CharField(blank=True, max_length=120, verbose_name="Poznámka")),
            ],
            options={
                "verbose_name": "Den bez svozu",
                "verbose_name_plural": "Dny bez svozu",
                "db_table": "waste_docs_noservicecalendarday",
                "ordering": ["closed_date"],
            },
        ),
    ]
