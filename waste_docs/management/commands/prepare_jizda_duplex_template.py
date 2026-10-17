from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from waste_docs.services.reports.excel_template_print_macro import ensure_jizda_print_template
from waste_docs.services.reports.protocol_print_settings import (
    PROTOCOL_PRINT_MACRO_NAME,
    template_has_printer_settings,
    template_has_vba_project,
)


class Command(BaseCommand):
    help = (
        "Připraví šablony jizda.xlsx (oboustranný tisk) a jizda.xlsm (makro TiskCelySesit) "
        "pomocí Microsoft Excel (Windows). LibreOffice nastavení tisku do souboru neukládá spolehlivě."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--template",
            default="",
            help="Cesta ke zdrojové šabloně jizda.xlsx (výchozí: BASE_DIR/jizda.xlsx).",
        )
        parser.add_argument(
            "--short-edge",
            action="store_true",
            help="Otočení přes kratší hranu (výchozí: delší hrana / landscape).",
        )

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        if options["template"]:
            template = Path(options["template"]).resolve()
            if not template.is_file():
                raise CommandError(f"Šablona neexistuje: {template}")
            base_dir = template.parent

        xlsx = base_dir / "jizda.xlsx"
        if not xlsx.is_file():
            raise CommandError(f"Šablona neexistuje: {xlsx}")

        try:
            primary, notes = ensure_jizda_print_template(
                base_dir,
                short_edge=bool(options["short_edge"]),
            )
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        xlsm = base_dir / "jizda.xlsm"

        if template_has_printer_settings(xlsx):
            self.stdout.write(
                self.style.SUCCESS(
                    f"{xlsx.name} má uložené printerSettings — oboustranný tisk se přenese do generovaných protokolů."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"{xlsx.name} stále nemá printerSettings. Zkuste v Excelu ručně uložit oboustranný tisk."
                )
            )

        if xlsm.is_file() and template_has_vba_project(xlsm):
            self.stdout.write(
                self.style.SUCCESS(
                    f"{xlsm.name} obsahuje makro — v Excelu Alt+F8 → {PROTOCOL_PRINT_MACRO_NAME} (tisk celého sešitu)."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Chybí {xlsm.name} s makrem {PROTOCOL_PRINT_MACRO_NAME}. "
                    "Tisk celého sešitu: v Excelu přidejte makro ActiveWorkbook.PrintOut a uložte jako .xlsm."
                )
            )

        for note in notes:
            self.stdout.write(self.style.WARNING(note))

        self.stdout.write(self.style.SUCCESS(f"Hlavní šablona pro generování: {primary.name}"))
