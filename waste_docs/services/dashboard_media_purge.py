from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.db import transaction

from waste_docs.models import PrintFileMark, Pruvodka
from waste_docs.services.ride_record_status import apply_pruvodka_status_after_save

logger = logging.getLogger(__name__)


@dataclass
class PurgeAllResult:
    pruvodky: int = 0
    zpo: int = 0
    protokoly: int = 0
    print_cache: int = 0
    print_marks: int = 0
    db_rides: int = 0

    @property
    def total_files(self) -> int:
        return self.pruvodky + self.zpo + self.protokoly + self.print_cache

    def summary_message(self) -> str:
        if self.total_files == 0 and self.print_marks == 0 and self.db_rides == 0:
            return "Ve vybraných adresářích nebyly nalezeny žádné vygenerované soubory ke smazání."
        parts: list[str] = []
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
        if self.db_rides:
            parts.append(f"jízd v DB vyčištěno: {self.db_rides}")
        return (
            "Uvolněno místo — smazáno ze všech adresářů (všechny dny): "
            + ", ".join(parts)
            + ". Soubory lze znovu vygenerovat."
        )


def _delete_files_under(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    deleted = 0
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        try:
            path.unlink()
            deleted += 1
        except OSError as exc:
            logger.warning("Smazání souboru %s selhalo: %s", path, exc)
    return deleted


def _delete_pruvodky_excel_files(pruvodky_dir: Path) -> int:
    if not pruvodky_dir.is_dir():
        return 0
    deleted = 0
    for path in pruvodky_dir.iterdir():
        if not path.is_file():
            continue
        try:
            path.unlink()
            deleted += 1
        except OSError as exc:
            logger.warning("Smazání průvodky %s selhalo: %s", path, exc)
    return deleted


def _clear_pruvodka_file_fields_in_db() -> int:
    updated = 0
    for ride in Pruvodka.objects.filter(is_archived=False).iterator():
        changed = False
        if ride.generated_file and getattr(ride.generated_file, "name", None):
            ride.generated_file = None
            changed = True
        if ride.zpo_instance_file and getattr(ride.zpo_instance_file, "name", None):
            ride.zpo_instance_file = None
            changed = True
        if not changed:
            continue
        apply_pruvodka_status_after_save(ride)
        ride.save(update_fields=("generated_file", "zpo_instance_file", "status"))
        updated += 1
    return updated


def purge_all_generated_artifacts() -> PurgeAllResult:
    result = PurgeAllResult()
    media_root = Path(settings.MEDIA_ROOT)

    with transaction.atomic():
        result.db_rides = _clear_pruvodka_file_fields_in_db()
        deleted_marks, _ = PrintFileMark.objects.all().delete()
        result.print_marks = deleted_marks

    result.pruvodky = _delete_pruvodky_excel_files(media_root / "pruvodky")
    result.zpo = _delete_files_under(media_root / "pruvodky" / "zpo_instance")
    result.protokoly = _delete_files_under(media_root / "protokoly")
    result.print_cache = _delete_files_under(media_root / "print_cache")

    return result
