"""Konfigurace Django `DATABASES['default']` z `DATABASE_URL` nebo výchozí SQLite."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

from config.env.sqlite_url import sqlite_path_from_database_url


def sqlite_options() -> dict:
    """WAL + busy timeout: snese souběžné zápisy (ASGI/uvicorn) bez 'database is locked'."""
    return {
        "timeout": 20,
        "transaction_mode": "IMMEDIATE",
        "init_command": (
            "PRAGMA journal_mode=WAL;"
            "PRAGMA synchronous=NORMAL;"
            "PRAGMA busy_timeout=20000;"
            "PRAGMA foreign_keys=ON;"
        ),
    }


def get_default_database_config(base_dir: Path) -> dict:
    """
    - Bez `DATABASE_URL`: SQLite `base_dir / db.sqlite3`
    - `sqlite:///…`: cesta ze URL
    - `postgres://` / `postgresql://`: PostgreSQL (psycopg 3)
    """
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": base_dir / "db.sqlite3",
            "OPTIONS": sqlite_options(),
        }
    lowered = url.lower()
    if lowered.startswith("sqlite:"):
        path = sqlite_path_from_database_url(url)
        if path is None:
            raise ImproperlyConfigured("Neplatná SQLite DATABASE_URL (očekává se sqlite:///cesta).")
        if not path.is_absolute():
            path = (base_dir / path).resolve()
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": path,
            "OPTIONS": sqlite_options(),
        }
    if lowered.startswith(("postgres://", "postgresql://")):
        return _postgres_config_from_url(url)
    raise ImproperlyConfigured(
        "Nepodporovaná DATABASE_URL (podporováno: sqlite:, postgres:, postgresql:)."
    )


def _postgres_config_from_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("Interní chyba: očekává se postgres URL.")
    db_name = unquote((parsed.path or "").lstrip("/"))
    if not db_name:
        raise ImproperlyConfigured("V DATABASE_URL chybí název databáze (cesta za hostitelem).")
    user = unquote(parsed.username) if parsed.username else ""
    password = unquote(parsed.password) if parsed.password else ""
    host = parsed.hostname or ""
    port = parsed.port or 5432
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": db_name,
        "USER": user,
        "PASSWORD": password,
        "HOST": host,
        "PORT": port,
        "CONN_MAX_AGE": 60,
    }
