from django.db import migrations, models


def init_sort_order(apps, schema_editor):
    VehicleKindCatalog = apps.get_model("catalogs", "VehicleKindCatalog")
    for i, row in enumerate(VehicleKindCatalog.objects.order_by("name", "pk")):
        row.sort_order = i * 10
        row.save(update_fields=["sort_order"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalogs", "0023_activitycatalog_evidence_without_excel"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehiclekindcatalog",
            name="sort_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="Nižší číslo = dříve v seznamech a ve sloupcích na dashboardu.",
                verbose_name="Pořadí",
            ),
        ),
        migrations.RunPython(init_sort_order, migrations.RunPython.noop),
    ]
