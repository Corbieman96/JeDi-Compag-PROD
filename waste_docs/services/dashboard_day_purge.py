from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from waste_docs.models import Pruvodka
from waste_docs.services.manual_print_marks import clear_all_print_marks_for_date
from waste_docs.services.pruvodka_generated_files import (
    clear_pruvodka_excel_file,
    delete_print_cache_for_media_rel,
    unlink_file_field,
)
from waste_docs.services.ride_bulk_actions import delete_protocol_files_for_rides, rides_for_day
from waste_docs.services.ride_protocol_xlsx import (
    PROTOCOL_SCOPE_DAY,
    protocol_filename_tokens_for_lookup,
    rides_for_protocol_day,
)
from waste_docs.services.ride_record_status import apply_pruvodka_status_after_save

logger = logging.getLogger(__name__)


@dataclass
class PurgeDayResult:
    pruvodky: int = 0
    zpo: int = 0
    protokoly: int = 0
    print_cache: int = 0
    print_marks: int = 0

    @property
    def total_files(self) -> int:
        return self.pruvodky + self.zpo + self.protokoly + self.print_cache

    def summary_message(self) -> str:
        if self.total_files == 0 and self.print_marks == 0:
            return "Pro vybraný den nebyly nalezeny žádné vygenerované soubory ke smazání."
        parts = []
        if self.pruvodky:
            parts.append(f"průvodek: {self.pruvodky}")
        if self.zpo:
            parts.append(f"ZPO: {self.zpo}")
        if self.protokoly:
            parts.append(f"protokolů: {self.protokoly}")
        if self.print_cache:
            parts.append(f"print cache: {self.print_cache}")
        if self.print_marks:
            parts.append(f"značek tisku: {self.print_marks}")
        return "Uvolněno místo — smazáno " + ", ".join(parts) + ". Soubory lze znovu vygenerovat."


def _protocol_dir():
    return settings.MEDIA_ROOT / "protokoly"


def purge_pruvodka_generated_files(ride: Pruvodka) -> tuple[bool, bool, bool, bool, int]:
    """Vrátí (pruvodka_soubor, zpo_soubor, pruvodka_vyčištěno, zpo_vyčištěno, print_cache_count)."""
    pruvodka_deleted = False
    zpo_deleted = False
    pruvodka_cleared = False
    zpo_cleared = False
    print_cache_count = 0
    if ride.generated_file and getattr(ride.generated_file, "name", None):
        pruvodka_deleted, pruvodka_cleared = clear_pruvodka_excel_file(ride)
        if pruvodka_deleted:
            print_cache_count += 1
    if ride.zpo_instance_file and getattr(ride.zpo_instance_file, "name", None):
        file_deleted, cache_deleted = unlink_file_field(ride.zpo_instance_file)
        if file_deleted:
            zpo_deleted = True
        if cache_deleted:
            print_cache_count += 1
        ride.zpo_instance_file = None
        zpo_cleared = True
    return pruvodka_deleted, zpo_deleted, pruvodka_cleared, zpo_cleared, print_cache_count


def _protocol_media_rels_before_delete(rides: list[Pruvodka], selected_date: date) -> list[str]:
    if not rides:
        return []
    tokens = protocol_filename_tokens_for_lookup(
        rides,
        scope=PROTOCOL_SCOPE_DAY,
        selected_date=selected_date,
    )
    protocol_dir = _protocol_dir()
    if not protocol_dir.exists():
        return []
    rels: list[str] = []
    seen: set[Path] = set()
    for token in tokens:
        for pattern in (f"protokol_{token}*.xlsx", f"poznamky_{token}*.pdf"):
            for path in protocol_dir.glob(pattern):
                if path in seen:
                    continue
                seen.add(path)
                try:
                    rels.append(path.relative_to(settings.MEDIA_ROOT).as_posix())
                except ValueError:
                    continue
    return rels


def purge_day_generated_artifacts(selected_date: date, user: AbstractBaseUser) -> PurgeDayResult:
    rides = rides_for_day(selected_date, user)
    protocol_rides = rides_for_protocol_day(selected_date, user)
    protocol_rels = _protocol_media_rels_before_delete(protocol_rides, selected_date)
    result = PurgeDayResult()

    with transaction.atomic():
        for ride in rides:
            pruvodka_deleted, zpo_deleted, pruvodka_cleared, zpo_cleared, cache_count = (
                purge_pruvodka_generated_files(ride)
            )
            if pruvodka_deleted:
                result.pruvodky += 1
            if zpo_deleted:
                result.zpo += 1
            result.print_cache += cache_count
            update_fields: list[str] = []
            if pruvodka_cleared:
                update_fields.append("generated_file")
            if zpo_cleared:
                update_fields.append("zpo_instance_file")
            if update_fields:
                apply_pruvodka_status_after_save(ride)
                update_fields.append("status")
                ride.save(update_fields=update_fields)

        result.protokoly += delete_protocol_files_for_rides(protocol_rides)
        marks_deleted, _ = clear_all_print_marks_for_date(selected_date)
        result.print_marks += marks_deleted

    for rel in protocol_rels:
        if rel.lower().endswith(".xlsx") and delete_print_cache_for_media_rel(rel):
            result.print_cache += 1

    return result
