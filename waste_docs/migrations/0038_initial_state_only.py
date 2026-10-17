# Přesun modelů CustomerRequest* do aplikace customer_requests (bez změny DB).

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("customer_requests", "0001_initial_state_only"),
        ("waste_docs", "0037_container_passport_and_pruvodka_fk"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="CustomerRequestAuditLog"),
                migrations.DeleteModel(name="CustomerRequestAttachment"),
                migrations.DeleteModel(name="CustomerRequest"),
            ],
        ),
    ]
