from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

ZPO_INSTANCE_DIR = "pruvodky/zpo_instance"


def zpo_instance_dir_path() -> Path:
    return Path(settings.MEDIA_ROOT) / "pruvodky" / "zpo_instance"


def referenced_zpo_instance_paths() -> set[str]:
    from waste_docs.models import Pruvodka

    out: set[str] = set()
    for name in Pruvodka.objects.exclude(zpo_instance_file="").values_list("zpo_instance_file", flat=True):
        if name:
            out.add(str(name).replace("\\", "/"))
    return out


def cleanup_zpo_instance_orphans_for_pruvodka(pk: int, keep_name: str = "") -> int:
    """Smaže soubory {pk}_* ve zpo_instance kromě keep_name."""
    keep = (keep_name or "").replace("\\", "/").strip()
    prefix = f"{pk}_"
    deleted = 0
    directory = zpo_instance_dir_path()
    if not directory.is_dir():
        return 0
    for path in directory.iterdir():
        if not path.is_file():
            continue
        if not path.name.startswith(prefix):
            continue
        rel = f"{ZPO_INSTANCE_DIR}/{path.name}"
        if keep and rel == keep:
            continue
        try:
            path.unlink()
            deleted += 1
        except OSError as exc:
            logger.warning("Smazání přebytečného ZPO %s selhalo: %s", rel, exc)
    return deleted


def cleanup_all_zpo_instance_orphans(*, dry_run: bool = False) -> tuple[int, int]:
    """
    Smaže soubory v media/pruvodky/zpo_instance/, které nejsou v DB u žádné průvodky.
    Vrací (smazané, nalezené osiřelé).
    """
    referenced = referenced_zpo_instance_paths()
    directory = zpo_instance_dir_path()
    if not directory.is_dir():
        return 0, 0
    orphans: list[Path] = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        rel = f"{ZPO_INSTANCE_DIR}/{path.name}"
        if rel not in referenced:
            orphans.append(path)
    if dry_run:
        return 0, len(orphans)
    deleted = 0
    for path in orphans:
        try:
            path.unlink()
            deleted += 1
        except OSError as exc:
            logger.warning("Smazání osiřelého ZPO %s selhalo: %s", path.name, exc)
    return deleted, len(orphans)


def save_zpo_instance_bytes(rel: str, payload: bytes) -> str:
    """Uloží ZPO na přesnou cestu rel (bez náhodného suffixu od storage.save)."""
    from django.core.files.base import ContentFile

    rel = rel.replace("\\", "/")
    if default_storage.exists(rel):
        default_storage.delete(rel)
    return default_storage.save(rel, ContentFile(payload))
