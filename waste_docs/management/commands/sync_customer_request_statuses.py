from django.core.management.base import BaseCommand

from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_status import sync_queryset


class Command(BaseCommand):
    help = "Synchronizuje stavy zákaznických požadavků podle reality navázaných jízd."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Jen spočítá požadavky, u kterých by se stav změnil (bez uložení).",
        )

    def handle(self, *args, **options):
        qs = CustomerRequest.objects.all().order_by("pk")
        if options["dry_run"]:
            from waste_docs.services.customer_request_status.sync import sync_customer_request_status

            would_update = 0
            for cr in qs.iterator():
                if sync_customer_request_status(cr, persist=False):
                    would_update += 1
            self.stdout.write(
                self.style.SUCCESS(f"Ke změně by bylo připraveno: {would_update} požadavků")
            )
            return

        updated = sync_queryset(qs)
        self.stdout.write(self.style.SUCCESS(f"Synchronizováno: {updated} požadavků"))
