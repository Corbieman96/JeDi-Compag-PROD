"""Testy zálohy hlavní SQLite databáze (core/services/db_backup.py)."""

from __future__ import annotations

import sqlite3
import tempfile
import time
from pathlib import Path

from django.test import SimpleTestCase
from django.utils import timezone

from core.services import db_backup
from core.services.db_backup import (
    BACKUP_DIR_NAME,
    BACKUP_SUFFIX,
    MAX_BACKUPS,
    backup_database,
    prune_backups,
)


def _make_sqlite(path: Path, value: str = "x") -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.execute("INSERT INTO t (v) VALUES (?)", (value,))
        conn.commit()
    finally:
        conn.close()


class DbBackupTests(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.src = self.base / "db.sqlite3"
        _make_sqlite(self.src, "hello")
        self.addCleanup(self._tmp.cleanup)

    def _backup_dir(self) -> Path:
        return self.base / BACKUP_DIR_NAME

    def test_backup_creates_dated_file(self):
        target = backup_database(base_dir=self.base, source_db=self.src)
        expected = timezone.localdate().strftime("%d_%m_%Y") + BACKUP_SUFFIX
        self.assertEqual(target.name, expected)
        self.assertTrue(target.is_file())
        self.assertEqual(target.parent, self._backup_dir())

    def test_backup_content_matches_source(self):
        target = backup_database(base_dir=self.base, source_db=self.src)
        conn = sqlite3.connect(str(target))
        try:
            row = conn.execute("SELECT v FROM t").fetchone()
        finally:
            conn.close()
        self.assertEqual(row[0], "hello")

    def test_same_day_backup_overwrites(self):
        backup_database(base_dir=self.base, source_db=self.src)
        backup_database(base_dir=self.base, source_db=self.src)
        files = list(self._backup_dir().glob(f"*{BACKUP_SUFFIX}"))
        self.assertEqual(len(files), 1)

    def test_missing_source_raises(self):
        with self.assertRaises(FileNotFoundError):
            backup_database(base_dir=self.base, source_db=self.base / "nope.sqlite3")

    def test_prune_keeps_only_max_backups(self):
        backup_dir = self._backup_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)
        names = [
            "01_01_2026_db.sqlite3",
            "02_01_2026_db.sqlite3",
            "03_01_2026_db.sqlite3",
            "04_01_2026_db.sqlite3",
        ]
        for i, n in enumerate(names):
            p = backup_dir / n
            _make_sqlite(p, n)
            # rozliš mtime, aby prune spolehlivě určil nejstarší
            import os

            os.utime(p, (time.time() + i, time.time() + i))

        removed = prune_backups(backup_dir)
        remaining = sorted(x.name for x in backup_dir.glob(f"*{BACKUP_SUFFIX}"))
        self.assertEqual(len(remaining), MAX_BACKUPS)
        self.assertEqual(len(removed), len(names) - MAX_BACKUPS)
        # nejstarší (index 0) musí být smazaný
        self.assertNotIn("01_01_2026_db.sqlite3", remaining)
