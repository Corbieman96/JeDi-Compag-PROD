# Generated manually for vehicle kind compatibility tree

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogs", "0046_containerpassport_volume_m3"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehiclekindcatalog",
            name="parent_kind",
            field=models.ForeignKey(
                blank=True,
                help_text="Např. 3H pod H, nebo H pod A. Potomci a předci se použijí při párování plánu, RZ a pasportů.",
                null=True,
                on_delete=models.SET_NULL,
                related_name="child_kinds",
                to="catalogs.vehiclekindcatalog",
                verbose_name="Nadřazený druh",
            ),
        ),
        migrations.AddField(
            model_name="vehiclekindcatalog",
            name="extra_compatible_kinds",
            field=models.ManyToManyField(
                blank=True,
                help_text="Ruční vazby mimo strom (obousměrně).",
                related_name="extra_compatible_with",
                to="catalogs.vehiclekindcatalog",
                verbose_name="Další kompatibilní druhy",
            ),
        ),
    ]
