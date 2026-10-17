from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from waste_docs.services.reports.protocol_pdf_fonts import (
    FALLBACK_FONT,
    normalize_xlsx_fonts,
)
from waste_docs.services.reports.protocol_print_settings import (
    resolve_protocol_template_path,
)


class Command(BaseCommand):
    help = (
        "Prepise neprenositelne fonty (Play, Aptos, Aptos Black) v sablone jizda.xlsx "
        "na Arial, aby se popisky neoriznuly pri prevodu na PDF. Commitnete jizda.xlsx do gitu."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--template",
            default="",
            help="Cesta ke sablone (vychozi: BASE_DIR/jizda.xlsx).",
        )

    def handle(self, *args, **options):
        template_arg = (options.get("template") or "").strip()
        template = (
            Path(template_arg) if template_arg else resolve_protocol_template_path()
        )

        if not template.is_file():
            self.stderr.write(f"Sablona neexistuje: {template}")
            return

        changed = normalize_xlsx_fonts(template)
        if changed:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{template.name}: fonty prepsany na {FALLBACK_FONT} "
                    f"(upraveno casti archivu: {changed}). Commitnete jizda.xlsx."
                )
            )
        else:
            self.stdout.write(
                f"{template.name}: zadne neprenositelne fonty k oprave (uz je Arial)."
            )
