"""Vytvoří zálohu hlavní SQLite databáze do adresáře Zaloha_db.

Určeno ke spouštění Plánovačem úloh Windows v nastaveném čase:
    python manage.py backup_db
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from core.services.db_backup import (
    BACKUP_DIR_NAME,
    MAX_BACKUPS,
    BACKUP_SUFFIX,
    backup_database,
)


class Command(BaseCommand):
    help = "Zálohuje hlavní databázi (db.sqlite3) do adresáře Zaloha_db."

    def handle(self, *args, **options):
        try:
            target = backup_database()
        except Exception as exc:  # noqa: BLE001 - hlásíme jako chybu příkazu
            raise CommandError(f"Záloha selhala: {exc}") from exc

        kept = sorted(target.parent.glob(f"*{BACKUP_SUFFIX}"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Záloha vytvořena: {target} "
                f"(adresář {BACKUP_DIR_NAME}, ponecháno {len(kept)}/{MAX_BACKUPS})"
            )
        )
