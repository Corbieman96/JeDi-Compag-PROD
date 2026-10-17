from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from waste_docs.services.reports.simplex_printer_blob import (
    RICOH_SIMPLEX_BLOB_PATH,
    capture_simplex_blob_for_ricoh,
    find_printer_by_substring,
    save_trusted_simplex_blob,
)


class Command(BaseCommand):
    help = (
        "Zachyti jednostranny printerSettings blob (DEVMODE) — volitelny fallback. "
        "Doporuceno: python manage.py prepare_jizda_simplex_template a commit jizda.xlsx."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--printer",
            default="RICOH",
            help='Nazev nebo cast nazvu tiskarny (vychozi: "RICOH").',
        )
        parser.add_argument(
            "--output",
            default="",
            help=f"Cilovy soubor (vychozi: {RICOH_SIMPLEX_BLOB_PATH}).",
        )

    def handle(self, *args, **options):
        needle = (options["printer"] or "RICOH").strip()
        printer_name = find_printer_by_substring(needle)
        if not printer_name:
            raise CommandError(
                f"Zadna tiskarna neodpovida {needle!r}. "
                "Nainstalujte ovladac RICOH IM C300 PCL 6 a spustte znovu."
            )

        self.stdout.write(f"Pouzivam tiskarnu: {printer_name}")

        try:
            blob = capture_simplex_blob_for_ricoh(needle)
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        output = (
            Path(options["output"]).resolve()
            if options["output"]
            else RICOH_SIMPLEX_BLOB_PATH
        )
        saved = save_trusted_simplex_blob(blob, output)
        self.stdout.write(
            self.style.SUCCESS(
                f"Ulozeno {saved} ({len(blob)} B). "
                "Pro produkci spiste: prepare_jizda_simplex_template a commit jizda.xlsx."
            )
        )
