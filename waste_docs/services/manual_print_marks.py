from __future__ import annotations

from datetime import date

from django.conf import settings
from django.contrib.auth.models import User

from waste_docs.models import Pruvodka
from waste_docs.models.print_file_mark import PrintFileMark


def file_row_key(*, kind: str, media_rel: str = "", path: str = "", label: str = "") -> str:
    rel = (media_rel or "").replace("\\", "/").lstrip("/")
    if rel:
        return f"{kind}:{rel}"
    normalized_path = (path or "").replace("\\", "/")
    if normalized_path:
        return f"{kind}:{normalized_path}"
    return f"{kind}:{label}"


def day_protocol_row_key(drive_date: date) -> str:
    return f"protocol:day:{drive_date.isoformat()}"


def day_protocol_notes_row_key(drive_date: date) -> str:
    return f"protocol_notes:day:{drive_date.isoformat()}"


def _zpo_row_key_from_stored_name(stored_name: str) -> str:
    rel = (stored_name or "").replace("\\", "/").lstrip("/")
    if not rel:
        return ""
    path = (settings.MEDIA_ROOT / rel).as_posix()
    return file_row_key(kind="zpo", path=path)


def row_keys_for_pruvodka(ride: Pruvodka) -> list[str]:
    keys: list[str] = []
    gf = ride.generated_file
    if gf and gf.name:
        keys.append(file_row_key(kind="xlsx", media_rel=gf.name))
    zf = ride.zpo_instance_file
    if zf and zf.name:
        zpo_path = ""
        try:
            zpo_path = zf.path
        except Exception:
            zpo_path = ""
        if zpo_path:
            keys.append(file_row_key(kind="zpo", path=zpo_path))
    return keys


def clear_row_marks_for_date(drive_date: date, row_key: str) -> int:
    key = (row_key or "").strip()
    if not key:
        return 0
    deleted, _ = PrintFileMark.objects.filter(drive_date=drive_date, row_key=key).delete()
    return deleted


def clear_pruvodka_print_marks(
    ride: Pruvodka,
    *,
    old_generated_rel: str = "",
    old_zpo_stored_name: str = "",
) -> None:
    if not ride.drive_date:
        return
    keys: set[str] = set(row_keys_for_pruvodka(ride))
    if old_generated_rel:
        keys.add(file_row_key(kind="xlsx", media_rel=old_generated_rel))
    if old_zpo_stored_name:
        old_key = _zpo_row_key_from_stored_name(old_zpo_stored_name)
        if old_key:
            keys.add(old_key)
    for key in keys:
        clear_row_marks_for_date(ride.drive_date, key)


def clear_protocol_marks_for_date(drive_date: date) -> int:
    deleted, _ = PrintFileMark.objects.filter(
        drive_date=drive_date,
        row_key__startswith="protocol:",
    ).delete()
    deleted_notes, _ = PrintFileMark.objects.filter(
        drive_date=drive_date,
        row_key__startswith="protocol_notes:",
    ).delete()
    return deleted + deleted_notes


def migrate_legacy_protocol_marks(user: User, drive_date: date) -> None:
    if not user.is_authenticated:
        return
    qs = PrintFileMark.objects.filter(user=user, drive_date=drive_date)
    legacy_protocol = [
        k for k in qs.values_list("row_key", flat=True)
        if k.startswith("protocol:") and not k.startswith("protocol:day:")
    ]
    legacy_notes = [
        k for k in qs.values_list("row_key", flat=True)
        if k.startswith("protocol_notes:") and not k.startswith("protocol_notes:day:")
    ]
    if legacy_protocol:
        mark_row_printed(user, drive_date, day_protocol_row_key(drive_date))
        PrintFileMark.objects.filter(
            user=user,
            drive_date=drive_date,
            row_key__in=legacy_protocol,
        ).delete()
    if legacy_notes:
        mark_row_printed(user, drive_date, day_protocol_notes_row_key(drive_date))
        PrintFileMark.objects.filter(
            user=user,
            drive_date=drive_date,
            row_key__in=legacy_notes,
        ).delete()


def printed_row_keys(user: User, drive_date: date) -> set[str]:
    if not user.is_authenticated:
        return set()
    return set(
        PrintFileMark.objects.filter(user=user, drive_date=drive_date).values_list(
            "row_key", flat=True
        )
    )


def mark_row_printed(user: User, drive_date: date, row_key: str) -> None:
    key = (row_key or "").strip()
    if not key or not user.is_authenticated:
        return
    PrintFileMark.objects.update_or_create(
        user=user,
        drive_date=drive_date,
        row_key=key,
        defaults={},
    )


def clear_protocol_marks(user: User, drive_date: date) -> None:
    if not user.is_authenticated:
        return
    PrintFileMark.objects.filter(
        user=user,
        drive_date=drive_date,
        row_key__startswith="protocol:",
    ).delete()
    PrintFileMark.objects.filter(
        user=user,
        drive_date=drive_date,
        row_key__startswith="protocol_notes:",
    ).delete()


def clear_all_print_marks_for_date(drive_date: date) -> tuple[int, int]:
    """Smaže všechny značky ručního tisku pro daný den (napříč uživateli)."""
    qs = PrintFileMark.objects.filter(drive_date=drive_date)
    count = qs.count()
    if count:
        qs.delete()
    return count, count
