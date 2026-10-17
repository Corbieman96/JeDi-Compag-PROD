# Generated manually for CustomerRequestVehicleKindClosure

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalogs", "0060_namesubjectwastesuffixpair_ride_note"),
        ("customer_requests", "0007_customerrequesttemplate_recurrence"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerRequestVehicleKindClosure",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("closure_date", models.DateField(db_index=True, verbose_name="Datum")),
                ("is_closed", models.BooleanField(default=True, verbose_name="Uzavřeno")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="customer_request_vehicle_kind_closures",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Naposledy změnil",
                    ),
                ),
                (
                    "vehicle_kind",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="customer_request_kind_closures",
                        to="catalogs.vehiclekindcatalog",
                        verbose_name="Druh vozidla",
                    ),
                ),
            ],
            options={
                "verbose_name": "Uzavření druhu vozidla pro požadavky",
                "verbose_name_plural": "Uzavření druhů vozidel pro požadavky",
                "db_table": "waste_docs_customerrequestvehiclekindclosure",
                "ordering": ["-closure_date", "vehicle_kind_id"],
            },
        ),
        migrations.AddConstraint(
            model_name="customerrequestvehiclekindclosure",
            constraint=models.UniqueConstraint(
                fields=("closure_date", "vehicle_kind"),
                name="uniq_cr_vehicle_kind_closure_day_kind",
            ),
        ),
    ]
