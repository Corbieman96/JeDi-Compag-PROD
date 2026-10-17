# Generated manually for follow-up parent link

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customer_requests", "0004_customer_request_template"),
    ]

    operations = [
        migrations.AddField(
            model_name="customerrequest",
            name="follow_up_parent_request",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="follow_up_child_requests",
                to="customer_requests.customerrequest",
                verbose_name="Základní požadavek (návaznost)",
            ),
        ),
    ]
