from django.conf import settings
from django.core.management.base import BaseCommand

from address_data.models import OfflineAddress
from address_data.services.osm_overpass import fetch_region_addresses
from catalogs.services.address import normalize_czech_address, normalize_czech_postal_code


class Command(BaseCommand):
    help = "Import full structured addresses from OpenStreetMap Overpass for configured regions."

    def add_arguments(self, parser):
        parser.add_argument("--replace", action="store_true", help="Delete existing addresses before import.")
        parser.add_argument(
            "--regions",
            nargs="+",
            help="Optional list of region names. Default is OFFLINE_ADDRESS_BOOTSTRAP_QUERIES.",
        )
        parser.add_argument(
            "--max-per-region",
            type=int,
            default=250000,
            help="Maximum addresses loaded for each region.",
        )

    def _save_rows(
        self,
        rows: list[dict],
        known_keys: set[tuple[str, str, str]] | None = None,
        batch_size: int = 2000,
    ) -> tuple[int, int]:
        created = 0
        skipped = 0
        pending: list[OfflineAddress] = []
        key_cache = known_keys if known_keys is not None else set()
        for row in rows:
            city = normalize_czech_address((row.get("city") or "").strip())
            street = normalize_czech_address((row.get("street") or "").strip())
            house_number = normalize_czech_address((row.get("house_number") or "").strip())
            if not city or not street or not house_number:
                skipped += 1
                continue
            row_key = (city, street, house_number)
            if row_key in key_cache:
                continue
            postal_code = normalize_czech_postal_code((row.get("postal_code") or "").strip())
            label = normalize_czech_address((row.get("label") or "").strip())
            if not label:
                label = normalize_czech_address(f"{street} {house_number}, {postal_code} {city}".strip())
            pending.append(
                OfflineAddress(
                    city=city,
                    street=street,
                    house_number=house_number,
                    postal_code=postal_code,
                    label=label.strip(", "),
                    lat=row["lat"],
                    lng=row["lng"],
                    city_norm=city.lower(),
                    street_norm=street.lower(),
                    label_norm=label.lower(),
                )
            )
            key_cache.add(row_key)
            if len(pending) >= batch_size:
                OfflineAddress.objects.bulk_create(pending, batch_size=batch_size)
                created += len(pending)
                pending.clear()
        if pending:
            OfflineAddress.objects.bulk_create(pending, batch_size=batch_size)
            created += len(pending)
        return created, skipped

    def handle(self, *args, **options):
        replace = bool(options["replace"])
        if options["replace"]:
            OfflineAddress.objects.all().delete()

        regions = options["regions"] or list(
            getattr(
                settings,
                "OFFLINE_ADDRESS_BOOTSTRAP_QUERIES",
                getattr(settings, "OFFLINE_ADDRESS_BOOTSTRAP_CITIES", []),
            )
        )
        max_per_region = max(5000, min(int(options["max_per_region"]), 500000))
        batch_size = 2000
        known_keys: set[tuple[str, str, str]]
        if replace:
            known_keys = set()
        else:
            known_keys = set(OfflineAddress.objects.values_list("city", "street", "house_number"))
        total_saved = 0
        total_skipped = 0
        for region in regions:
            self.stdout.write(f"Načítám region: {region}")
            rows = fetch_region_addresses(region_name=region, max_rows=max_per_region)
            saved, skipped = self._save_rows(rows, known_keys=known_keys, batch_size=batch_size)
            total_saved += saved
            total_skipped += skipped
            self.stdout.write(f"  uloženo: {saved}, přeskočeno: {skipped}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Import hotov. Celkem uloženo: {total_saved}, přeskočeno: {total_skipped}, "
                f"stav DB: {OfflineAddress.objects.count()} adres."
            )
        )
