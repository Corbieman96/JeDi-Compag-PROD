from django.conf import settings
from django.core.management.base import BaseCommand

from address_data.models import OfflineAddress
from address_data.services.offline_persist import bulk_save_rows
from address_data.services.ruian_import import iter_region_addresses


class Command(BaseCommand):
    help = "Import structured Czech addresses from RÚIAN MapServer for configured regions."

    def add_arguments(self, parser):
        parser.add_argument("--replace", action="store_true", help="Delete existing addresses before import.")
        parser.add_argument(
            "--regions",
            nargs="+",
            help="Optional list of region names. Default is OFFLINE_ADDRESS_RUIAN_REGIONS.",
        )
        parser.add_argument(
            "--max-per-region",
            type=int,
            default=None,
            help="Maximum addresses loaded for each region.",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip rows that already exist in the database.",
        )

    def handle(self, *args, **options):
        if options["replace"]:
            OfflineAddress.objects.all().delete()

        regions = options["regions"] or list(getattr(settings, "OFFLINE_ADDRESS_RUIAN_REGIONS", []))
        if not regions:
            self.stderr.write(self.style.ERROR("No regions configured (OFFLINE_ADDRESS_RUIAN_REGIONS)."))
            return

        default_max = int(getattr(settings, "OFFLINE_ADDRESS_RUIAN_MAX_PER_REGION", 600_000))
        max_per_region = options["max_per_region"] if options["max_per_region"] is not None else default_max
        max_per_region = max(1000, min(int(max_per_region), 1_000_000))
        batch_size = 2000

        if options["replace"]:
            known_keys: set[tuple[str, str, str]] = set()
        elif options["skip_existing"]:
            known_keys = set(OfflineAddress.objects.values_list("city", "street", "house_number"))
        else:
            known_keys = set()

        total_saved = 0
        total_skipped = 0
        for region in regions:
            self.stdout.write(f"Načítám kraj: {region}")
            region_saved = 0
            region_skipped = 0
            batch: list[dict] = []
            for row in iter_region_addresses(region_name=region, max_rows=max_per_region):
                batch.append(row)
                if len(batch) >= batch_size:
                    saved, skipped = bulk_save_rows(batch, known_keys=known_keys, batch_size=batch_size)
                    region_saved += saved
                    region_skipped += skipped
                    total_saved += saved
                    total_skipped += skipped
                    batch.clear()
                    self.stdout.write(f"  {region}: průběžně {region_saved}…", ending="\r")
            if batch:
                saved, skipped = bulk_save_rows(batch, known_keys=known_keys, batch_size=batch_size)
                region_saved += saved
                region_skipped += skipped
                total_saved += saved
                total_skipped += skipped
            self.stdout.write(f"  {region}: uloženo {region_saved}, přeskočeno {region_skipped}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Import hotov. Celkem uloženo: {total_saved}, přeskočeno: {total_skipped}, "
                f"stav DB: {OfflineAddress.objects.count()} adres."
            )
        )
