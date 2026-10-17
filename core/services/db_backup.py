"""Jednoduchá záloha hlavní SQLite databáze do adresáře Zaloha_db.

Kopíruje pouze default DB (db.sqlite3) přes online backup API SQLite,
aby nevznikl porušený soubor při souběžném zápisu. Uchovává max 3 zálohy
(nejstarší se maže), jednu za den (soubor téhož dne se přepíše).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from django.conf import settings
from django.db import connections
from django.utils import timezone

BACKUP_DIR_NAME = "Zaloha_db"
MAX_BACKUPS = 3
BACKUP_SUFFIX = "_db.sqlite3"


def _default_db_path() -> Path:
    name = connections["default"].settings_dict.get("NAME")
    return Path(name)


def _backup_dir(base_dir: Path | None = None) -> Path:
    base = Path(base_dir) if base_dir is not None else Path(settings.BASE_DIR)
    return base / BACKUP_DIR_NAME


def _backup_filename(day=None) -> str:
    day = day or timezone.localdate()
    return f"{day.strftime('%d_%m_%Y')}{BACKUP_SUFFIX}"


def prune_backups(backup_dir: Path, *, max_backups: int = MAX_BACKUPS) -> list[Path]:
    """Ponechá jen nejnovější zálohy, starší smaže. Vrací smazané cesty."""
    files = sorted(
        backup_dir.glob(f"*{BACKUP_SUFFIX}"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    removed: list[Path] = []
    for old in files[max_backups:]:
        try:
            old.unlink()
            removed.append(old)
        except OSError:
            pass
    return removed


def backup_database(
    *, base_dir: Path | None = None, source_db: Path | None = None
) -> Path:
    """Vytvoří zálohu default DB do Zaloha_db a prořeže na max 3. Vrací cílovou cestu."""
    src = Path(source_db) if source_db is not None else _default_db_path()
    if not src.is_file():
        raise FileNotFoundError(f"Zdrojová databáze nenalezena: {src}")

    backup_dir = _backup_dir(base_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / _backup_filename()

    source_conn = sqlite3.connect(str(src))
    try:
        dest_conn = sqlite3.connect(str(target))
        try:
            source_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        source_conn.close()

    prune_backups(backup_dir)
    return target
