"""Validace a pomocné funkce pro navazující činnost u požadavku."""

from __future__ import annotations

from datetime import date, timedelta


def follow_up_target_date_error(target_date: date | None, follow_up_target_date: date | None) -> str | None:
    if not follow_up_target_date or not target_date:
        return None
    min_follow_date = target_date + timedelta(days=1)
    if follow_up_target_date < min_follow_date:
        return "Datum navazující činnosti musí být minimálně o 1 den po datu požadavku."
    return None
