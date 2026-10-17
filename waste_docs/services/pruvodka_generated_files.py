from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings

from waste_docs.models import Pruvodka
from waste_docs.pruvodka_services import generate_xlsx
from waste_docs.services.manual_print_marks import clear_pruvodka_print_marks
from waste_docs.services.reports.xlsx_to_pdf import _cache_path_for_rel
from waste_docs.services.ride_print_order import sort_rides_list
from waste_docs.services.ride_record_status import apply_pruvodka_status_after_save

logger = logging.getLogger(__name__)


def should_generate_excel(ride: Pruvodka) -> bool:
    return not bool(ride.activity and ride.activity.evidence_without_excel)


def has_generated_excel_file(ride: Pruvodka) -> bool:
    if not ride.generated_file:
        return False
    try:
        return bool(ride.generated_file.name) and ride.generated_file.storage.exists(ride.generated_file.name)
    except Exception:
        return False


def delete_print_cache_for_media_rel(media_rel: str) -> bool:
    rel = (media_rel or "").replace("\\", "/").lstrip("/")
    if not rel:
        return False
    cache_path = _cache_path_for_rel(rel)
    if not cache_path.is_file():
        return False
    try:
        cache_path.unlink()
        return True
    except OSError as exc:
        logger.warning("Smazání print cache %s selhalo: %s", cache_path, exc)
        return False


def unlink_file_field(file_field) -> tuple[bool, bool]:
    """Vrátí (soubor_smazán, print_cache_smazána)."""
    name = getattr(file_field, "name", None) if file_field else None
    if not name:
        return False, False
    rel = str(name).replace("\\", "/").lstrip("/")
    file_deleted = False
    try:
        if file_field.storage.exists(name):
            file_field.storage.delete(name)
            file_deleted = True
    except Exception as exc:
        logger.warning("Smazání souboru %s selhalo: %s", name, exc)
    cache_deleted = delete_print_cache_for_media_rel(rel)
    return file_deleted, cache_deleted


def clear_pruvodka_excel_file(ride: Pruvodka) -> tuple[bool, bool]:
    """Smaže Excel průvodku a print cache. Vrátí (soubor_smazán, db_vyčištěno)."""
    if not ride.generated_file or not getattr(ride.generated_file, "name", None):
        return False, False
    file_deleted, _cache_deleted = unlink_file_field(ride.generated_file)
    ride.generated_file = None
    return file_deleted, True


def regenerate_pruvodka_excel(ride: Pruvodka) -> Path | None:
    """Smaže starý Excel průvodky a vygeneruje nový z aktuálních dat DB."""
    cleared = False
    if ride.generated_file and getattr(ride.generated_file, "name", None):
        clear_pruvodka_excel_file(ride)
        cleared = True

    if not should_generate_excel(ride):
        if cleared:
            apply_pruvodka_status_after_save(ride)
            ride.save(update_fields=("generated_file", "status"))
        return None

    path = generate_xlsx(ride)
    relative_path = Path(path).relative_to(settings.MEDIA_ROOT)
    ride.generated_file.name = str(relative_path).replace("\\", "/")
    apply_pruvodka_status_after_save(ride)
    ride.save(update_fields=("generated_file", "status"))
    clear_pruvodka_print_marks(ride)
    from waste_docs.services.customer_request_status import sync_for_pruvodka

    sync_for_pruvodka(ride)
    return Path(path)


def ensure_pruvodka_excel(ride: Pruvodka) -> Path | None:
    """Vygeneruje Excel průvodky jen pokud soubor chybí (existující se nemazá)."""
    if has_generated_excel_file(ride):
        return None
    if not should_generate_excel(ride):
        return None

    path = generate_xlsx(ride)
    relative_path = Path(path).relative_to(settings.MEDIA_ROOT)
    ride.generated_file.name = str(relative_path).replace("\\", "/")
    apply_pruvodka_status_after_save(ride)
    ride.save(update_fields=("generated_file", "status"))
    from waste_docs.services.customer_request_status import sync_for_pruvodka

    sync_for_pruvodka(ride)
    return Path(path)


def rides_missing_excel(rides: list[Pruvodka]) -> list[Pruvodka]:
    return [
        ride
        for ride in sort_rides_list(rides)
        if should_generate_excel(ride) and not has_generated_excel_file(ride)
    ]


def count_rides_missing_excel(rides: list[Pruvodka]) -> int:
    return len(rides_missing_excel(rides))


def ensure_excel_files_for_rides(rides: list[Pruvodka]) -> int:
    generated_count = 0
    for ride in sort_rides_list(rides):
        if ensure_pruvodka_excel(ride) is not None:
            generated_count += 1
    return generated_count


def regenerate_all_excels(rides: list[Pruvodka]) -> int:
    rides = sort_rides_list(rides)
    generated_count = 0
    for ride in rides:
        if regenerate_pruvodka_excel(ride) is not None:
            generated_count += 1
    return generated_count
