"""Po hard-delete chybového logu uvolní místo v SQLite souboru (VACUUM)."""

from __future__ import annotations

import logging

from django.db import connection, transaction
from django.db.utils import OperationalError

logger = logging.getLogger(__name__)


def reclaim_sqlite_space_after_delete() -> None:
    """Řádky jsou už smazané; u SQLite ještě zmenší soubor DB, pokud to jde."""
    if connection.vendor != "sqlite":
        return
    if connection.in_atomic_block:
        transaction.on_commit(_run_vacuum)
        return
    _run_vacuum()


def _run_vacuum() -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute("VACUUM")
    except OperationalError:
        logger.warning(
            "SQLite VACUUM po smazání chybového logu se nepodařil (databáze může být zamčená)."
        )
