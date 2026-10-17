"""Import pasportů kontejnerů z ODS (VOK — Doplněná tabulka)."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from catalogs.services.container_passport_vok_import import import_container_passports_from_ods


class Command(BaseCommand):
    help = (
        "Načte ODS „VOK - tabulka - Doplněná.ods“ (nebo --path) a vytvoří/aktualizuje pasporty kontejnerů. "
        "Objem z sloupce m³ → pole Objem (m³); při ≥ 30 m³ doplní požadavek 3H. Druh vozidla musí sedět s "
        "/catalogs/vehicle-rz/kinds/ (zkratka z názvu listu nebo VOK_IMPORT_SHEET_KIND_MAP)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default="",
            help="Cesta k .ods (výchozí: VOK - tabulka - Doplněná.ods v kořeni projektu).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Jen ověřit řádky, nic neukládat.",
        )

    def handle(self, *args, **options):
        raw = (options.get("path") or "").strip()
        path = Path(raw) if raw else (settings.BASE_DIR / "VOK - tabulka - Doplněná.ods")
        if not path.is_file():
            self.stderr.write(self.style.ERROR(f"Soubor neexistuje: {path}"))
            return
        dry = bool(options.get("dry_run"))
        res = import_container_passports_from_ods(path, dry_run=dry)
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Náhled' if dry else 'Hotovo'}: vytvořeno {res.created}, aktualizováno {res.updated}, "
                f"řádků OK v náhledu {res.preview_ok}, přeskočeno {res.skipped}, listů bez hlavičky {res.sheet_skipped}."
            )
        )
        for e in res.errors[:80]:
            self.stdout.write(self.style.WARNING(e))
        if len(res.errors) > 80:
            self.stdout.write(self.style.WARNING(f"… a dalších {len(res.errors) - 80} hlášení."))
