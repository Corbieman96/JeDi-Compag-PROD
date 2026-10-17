from django.core.management.base import BaseCommand
from django.utils import timezone

from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_status.sync import sync_invoice_overdue_status


class Command(BaseCommand):
    help = "Označí zákaznické požadavky po splatnosti zálohy jako invoice_overdue."

    def handle(self, *args, **options):
        today = timezone.localdate()
        qs = CustomerRequest.objects.select_related("created_by").filter(
            requires_advance_invoice=True,
            status=CustomerRequest.Status.SUBMITTED,
            invoice_due_date__lt=today,
        )
        updated = 0
        for item in qs:
            if sync_invoice_overdue_status(item, today=today):
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Označeno po splatnosti: {updated}"))
