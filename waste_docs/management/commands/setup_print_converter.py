from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from waste_docs.services.reports.libreoffice_setup import (
    DEFAULT_INSTALL_DIR,
    install_portable_libreoffice,
    portable_soffice_path,
)
from waste_docs.services.reports.xlsx_to_pdf import _find_soffice


class Command(BaseCommand):
    help = (
        "Nainstaluje portable LibreOffice do tools/LibreOfficePortable "
        "(bez admin práv) pro převod XLSX→PDF při tisku."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--install-dir",
            default=str(DEFAULT_INSTALL_DIR),
            help="Cílová složka pro portable LibreOffice.",
        )
        parser.add_argument(
            "--check-only",
            action="store_true",
            help="Jen zobrazí dostupný soffice.exe, nic neinstaluje.",
        )

    def handle(self, *args, **options):
        install_dir = Path(options["install_dir"])
        if options["check_only"]:
            found = _find_soffice() or portable_soffice_path(install_dir)
            if found is None:
                raise CommandError(
                    "LibreOffice (soffice.exe) není k dispozici. "
                    "Spusťte: python manage.py setup_print_converter"
                )
            self.stdout.write(self.style.SUCCESS(f"Nalezeno: {found}"))
            return

        try:
            soffice = install_portable_libreoffice(install_dir)
        except OSError as exc:
            raise CommandError(str(exc)) from exc
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"LibreOffice připraven: {soffice}"))
        self.stdout.write(
            "Volitelně do .env:\n"
            f"LIBREOFFICE_SOFFICE_PATH={soffice}"
        )
