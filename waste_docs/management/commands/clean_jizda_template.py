from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from waste_docs.services.reports.protocol_print_settings import (
    repair_worksheet_drawings_in_xlsx,
    strip_printer_settings_from_xlsx,
    template_has_printer_settings,
)
from waste_docs.services.reports.protocol_sheet_bounds import (
    PROTOCOL_SHEET_MAX_COL,
    PROTOCOL_SHEET_MAX_ROW,
    trim_protocol_sheet_to_bounds,
)

try:
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover
    load_workbook = None  # type: ignore[assignment,misc]


class Command(BaseCommand):
    help = (
        "Odstraní ghost řádky/sloupce pod layoutem protokolu (A1:M38) ze šablony jizda.xlsx. "
        "Page setup a tisk nemění — nastavte v Excelu."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--template",
            default="",
            help="Cesta ke šabloně (výchozí: BASE_DIR/jizda.xlsx).",
        )

    def handle(self, *args, **options):
        if load_workbook is None:
            raise CommandError("Knihovna openpyxl není nainstalovaná.")

        template = Path(options["template"]).resolve() if options["template"] else Path(settings.BASE_DIR) / "jizda.xlsx"
        if not template.is_file():
            raise CommandError(f"Šablona neexistuje: {template}")

        wb = load_workbook(template)
        ws = wb.active
        before_row = ws.max_row
        before_col = ws.max_column
        trim_protocol_sheet_to_bounds(ws)
        wb.save(template)
        wb.close()

        stripped = strip_printer_settings_from_xlsx(template)
        repaired = repair_worksheet_drawings_in_xlsx(template)

        msg = f"{template.name}: orez {before_row}x{before_col} -> {PROTOCOL_SHEET_MAX_ROW}x{PROTOCOL_SHEET_MAX_COL} (A1:M38)"
        extras = []
        if stripped:
            extras.append("printerSettings odstraneny")
        if repaired:
            extras.append("drawing r:id opraveno")
        if extras:
            msg += "; " + ", ".join(extras)
        self.stdout.write(self.style.SUCCESS(msg))
