import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from address_data.models import OfflineAddress
from catalogs.services.address import normalize_czech_address


class Command(BaseCommand):
    help = "Import addresses into addresses.sqlite3 from CSV."

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="CSV file path.")
        parser.add_argument("--replace", action="store_true", help="Delete existing addresses before import.")

    def handle(self, *args, **options):
        file_path = Path(options["file_path"])
        if not file_path.exists():
            raise CommandError(f"Soubor neexistuje: {file_path}")
        if file_path.suffix.lower() != ".csv":
            raise CommandError("Podporovaný je zatím pouze CSV soubor.")

        if options["replace"]:
            OfflineAddress.objects.all().delete()

        created = 0
        with file_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            required = {"label", "lat", "lng"}
            if not required.issubset(set(reader.fieldnames or [])):
                raise CommandError("CSV musí obsahovat sloupce: label, lat, lng")
            for row in reader:
                label = normalize_czech_address((row.get("label") or "").strip())
                if not label:
                    continue
                city = (row.get("city") or "").strip()
                street = (row.get("street") or "").strip()
                house_number = (row.get("house_number") or "").strip()
                postal_code = (row.get("postal_code") or "").strip()
                try:
                    lat = float((row.get("lat") or "").replace(",", "."))
                    lng = float((row.get("lng") or "").replace(",", "."))
                except ValueError:
                    continue

                OfflineAddress.objects.update_or_create(
                    label=label,
                    defaults={
                        "city": city,
                        "street": street,
                        "house_number": house_number,
                        "postal_code": postal_code,
                        "lat": lat,
                        "lng": lng,
                        "city_norm": normalize_czech_address(city).lower(),
                        "street_norm": normalize_czech_address(street).lower(),
                        "label_norm": label.lower(),
                    },
                )
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Import dokončen, zpracováno řádků: {created}"))
