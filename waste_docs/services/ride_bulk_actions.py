from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User

from users.services.access import can_see_all_waste_docs
from waste_docs.models import Pruvodka
from waste_docs.services.pruvodka_generated_files import ensure_excel_files_for_rides, has_generated_excel_file
from waste_docs.services.reports.protocol_note_overflow import (
    build_protocol_note_supplement_pdf_bytes,
    rides_needing_note_supplement,
)
from waste_docs.services.manual_print_marks import (
    clear_protocol_marks_for_date,
    day_protocol_notes_row_key,
    day_protocol_row_key,
    file_row_key,
)
from waste_docs.services.ride_print_order import order_rides_queryset
from waste_docs.services.reports.media_download import (
    MediaDownloadError,
    media_download_url_for_rel,
)
from waste_docs.services.reports.xlsx_to_pdf import convert_xlsx_to_pdf, print_url_for_media_rel
from waste_docs.services.ride_protocol_xlsx import (
    PROTOCOL_SCOPE_DAY,
    PROTOCOL_SCOPE_GROUP,
    generate_protocol_xlsx,
    protocol_file_is_stale,
    protocol_filename_token,
    protocol_filename_tokens_for_lookup,
)
from waste_docs.ride_print_service import build_ride_print_rows
from waste_docs.services.pruvodka_pair_docs import pair_docs_for_pruvodka
from waste_docs.services.zpo_instance_status import explain_missing_zpo_instance
from waste_docs.zpo_instance_generator import ensure_zpo_instance_for_pruvodka_pk
from waste_docs.zpo_policy import system_may_generate_zpo_instance
from waste_docs.zpo_resolved import display_zpo_file_for_pruvodka, effective_zpo_file
from pio.services import effective_pio_file


def rides_for_day(selected_date: date, user: User) -> list[Pruvodka]:
    return rides_for_print_scope(selected_date, user)


def rides_for_print_scope(
    selected_date: date,
    user: User,
    *,
    vehicle_rz_id: int = 0,
    filter_pks: list[int] | None = None,
    for_email_package: bool = False,
    driver_id: int | None = None,
) -> list[Pruvodka]:
    if vehicle_rz_id > 0 and not for_email_package:
        from waste_docs.services.ride_document_email.exclusions import is_group_emailed

        if is_group_emailed(selected_date, vehicle_rz_id):
            return []
        qs = Pruvodka.objects.filter(
            drive_date=selected_date,
            vehicle_rz_id=vehicle_rz_id,
            is_archived=False,
        )
    else:
        qs = Pruvodka.objects.filter(drive_date=selected_date, is_archived=False)
    if driver_id is not None and not filter_pks:
        if driver_id > 0:
            qs = qs.filter(driver_id=driver_id)
        else:
            qs = qs.filter(driver_id__isnull=True)
    qs = order_rides_queryset(qs.select_related("activity"))
    if filter_pks:
        qs = qs.filter(pk__in=filter_pks)
    if not can_see_all_waste_docs(user):
        qs = qs.filter(created_by=user)
    return list(qs)


def build_merged_print_file_rows(
    selected_date: date,
    user: User,
    *,
    vehicle_rz_id: int = 0,
    filter_pks: list[int] | None = None,
    driver_id: int | None = None,
) -> list[dict]:
    from waste_docs.services.manual_print_marks import migrate_legacy_protocol_marks
    from waste_docs.services.ride_protocol_xlsx import rides_for_protocol_day, rides_for_protocol_group

    rides = rides_for_print_scope(
        selected_date,
        user,
        vehicle_rz_id=vehicle_rz_id,
        filter_pks=filter_pks,
        driver_id=driver_id,
    )
    if not rides:
        if vehicle_rz_id > 0:
            return []
        protocol_rides = rides_for_protocol_day(selected_date, user)
        file_rows = append_day_protocol_file(
            [],
            protocol_rides,
            selected_date,
            generate_if_missing=False,
        )
        migrate_legacy_protocol_marks(user, selected_date)
        return file_rows
    from waste_docs.services.print_bundle_prepare import prepare_print_bundle_files

    prepare_print_bundle_files(rides)
    _print_rows, file_rows, _zpo_warnings = build_print_rows_and_files(rides)
    if vehicle_rz_id > 0:
        protocol_rides = rides_for_protocol_group(
            selected_date,
            vehicle_rz_id,
            user,
            filter_pks=filter_pks,
            driver_id=driver_id,
        )
        if filter_pks:
            protocol_rides = [ride for ride in protocol_rides if ride.pk in filter_pks]
        file_rows = append_protocol_and_supplement_file_rows(
            file_rows,
            protocol_rides,
            selected_date,
            scope=PROTOCOL_SCOPE_GROUP,
            generate_if_missing=False,
        )
    else:
        protocol_rides = rides_for_protocol_day(selected_date, user)
        file_rows = append_day_protocol_file(
            file_rows,
            protocol_rides,
            selected_date,
            generate_if_missing=False,
        )
    migrate_legacy_protocol_marks(user, selected_date)
    return file_rows


def _protocol_path_for_display(protocol_path: Path) -> Path:
    """Preferuje existující PDF; XLSX→PDF konverzi neprovádí (ta patří jen k Generovat protokol)."""
    protocol_path = Path(protocol_path)
    if protocol_path.suffix.lower() == ".pdf":
        return protocol_path
    pdf_path = _protocol_pdf_path_for_xlsx(protocol_path)
    if pdf_path.is_file():
        return pdf_path
    return protocol_path


def _media_url(rel: str) -> str:
    return f"{settings.MEDIA_URL.rstrip('/')}/{rel}"


def _ride_row_meta(ride: Pruvodka) -> dict[str, str]:
    return {
        "vehicle_rz": (ride.vehicle_rz_snapshot or "").strip() or "—",
        "driver": (ride.driver_snapshot or "").strip() or "—",
        "kdo": (ride.name_snapshot or "").strip() or "—",
        "odpad": (ride.waste_type_snapshot or "").strip() or "—",
    }


def _file_row(
    *,
    kind: str,
    label: str,
    url: str,
    path: str = "",
    media_rel: str = "",
    warning: bool = False,
    vehicle_rz: str = "",
    driver: str = "",
    kdo: str = "",
    odpad: str = "",
    row_key: str = "",
) -> dict:
    key = row_key or file_row_key(kind=kind, media_rel=media_rel, path=path, label=label)
    row = {
        "kind": kind,
        "label": label,
        "url": url,
        "path": path,
        "print_url": url,
        "row_key": key,
        "vehicle_rz": vehicle_rz,
        "driver": driver,
        "kdo": kdo,
        "odpad": odpad,
    }
    if warning:
        row["warning"] = True
    if media_rel:
        row["media_rel"] = media_rel.replace("\\", "/").lstrip("/")
    if media_rel and kind == "xlsx":
        # Otevřít XLSX přes login view; tisk zůstává XLSX→PDF.
        try:
            row["url"] = media_download_url_for_rel(media_rel)
            row["print_url"] = print_url_for_media_rel(media_rel)
        except MediaDownloadError:
            pass
    if media_rel and kind in ("zpo", "pio"):
        try:
            served = media_download_url_for_rel(media_rel)
            row["url"] = served
            row["print_url"] = served
        except MediaDownloadError:
            pass
    if media_rel and kind in ("protocol", "protocol_notes"):
        # Může být PDF i XLSX (PDF ještě nevygenerované). /media/ při DEBUG=False nefunguje.
        try:
            row["url"] = media_download_url_for_rel(media_rel)
            if media_rel.lower().endswith(".xlsx"):
                row["print_url"] = print_url_for_media_rel(media_rel)
            else:
                row["print_url"] = row["url"]
        except MediaDownloadError:
            pass
    return row


def build_print_rows_and_files(
    rides: list[Pruvodka],
    *,
    ensure_zpo: bool = False,
    for_email_package: bool = False,
    include_pio: bool = True,
) -> tuple[list[dict], list[dict], list[str]]:
    print_rows = build_ride_print_rows(rides)
    file_rows: list[dict] = []
    zpo_warnings: list[str] = []
    for row in print_rows:
        ride = row["ride"]
        if not for_email_package and ride.vehicle_rz_id:
            from waste_docs.services.ride_document_email.exclusions import is_group_emailed

            if is_group_emailed(ride.drive_date, ride.vehicle_rz_id):
                continue
        pair_docs = pair_docs_for_pruvodka(ride)
        snd = (ride.snd_cislo_listu or "").strip()
        row_meta = _ride_row_meta(ride)

        if has_generated_excel_file(ride):
            media_rel = ride.generated_file.name.replace("\\", "/").lstrip("/")
            file_rows.append(
                _file_row(
                    kind="xlsx",
                    label=f"Průvodka (Excel) #{ride.pk} ({snd or '-'})",
                    url=ride.generated_file.url,
                    path=ride.generated_file.path,
                    media_rel=media_rel,
                    **row_meta,
                )
            )

        zpo_f = display_zpo_file_for_pruvodka(ride, pair_docs)
        can_ensure = system_may_generate_zpo_instance(ride) and effective_zpo_file(pair_docs)

        if zpo_f or can_ensure:
            if can_ensure and (ensure_zpo or not zpo_f):
                ensure_zpo_instance_for_pruvodka_pk(ride.pk)
                ride.refresh_from_db()
                zpo_f = display_zpo_file_for_pruvodka(ride, pair_docs)
            if zpo_f:
                zpo_path = ""
                zpo_rel = ""
                try:
                    zpo_path = zpo_f.path
                except Exception:
                    zpo_path = ""
                try:
                    zpo_rel = (zpo_f.name or "").replace("\\", "/").lstrip("/")
                except Exception:
                    zpo_rel = ""
                file_rows.append(
                    _file_row(
                        kind="zpo",
                        label=f"ZPO #{ride.pk} ({snd or '-'})",
                        url=zpo_f.url,
                        path=zpo_path,
                        media_rel=zpo_rel,
                        **row_meta,
                    )
                )
            elif snd and can_ensure:
                reason = explain_missing_zpo_instance(ride, pair=pair_docs) or "generování selhalo"
                zpo_warnings.append(f"#{ride.pk} ({snd}): {reason}")
                file_rows.append(
                    _file_row(
                        kind="zpo",
                        label=f"ZPO #{ride.pk} ({snd}) — {reason}",
                        url="",
                        path="",
                        warning=True,
                        **row_meta,
                    )
                )
        pio_f = effective_pio_file(pair_docs) if include_pio else None
        if pio_f:
            pio_path = ""
            pio_rel = ""
            try:
                pio_path = pio_f.path
            except Exception:
                pio_path = ""
            try:
                pio_rel = (pio_f.name or "").replace("\\", "/").lstrip("/")
            except Exception:
                pio_rel = ""
            file_rows.append(
                _file_row(
                    kind="pio",
                    label=f"PIO k jízdě #{ride.pk}",
                    url=pio_f.url,
                    path=pio_path,
                    media_rel=pio_rel,
                    **row_meta,
                )
            )
    return print_rows, file_rows, zpo_warnings


def _protocol_dir() -> Path:
    return settings.MEDIA_ROOT / "protokoly"


def _protocol_pdf_path_for_xlsx(protocol_xlsx_path: Path) -> Path:
    return protocol_xlsx_path.with_suffix(".pdf")


def _ensure_protocol_pdf(protocol_xlsx_path: Path) -> Path:
    """Použije existující převod XLSX→PDF z modalu tisku a uloží stabilní PDF protokol."""
    protocol_xlsx_path = Path(protocol_xlsx_path)
    media_rel = protocol_xlsx_path.relative_to(settings.MEDIA_ROOT).as_posix()
    cached_pdf = convert_xlsx_to_pdf(protocol_xlsx_path, media_rel=media_rel)
    protocol_pdf_path = _protocol_pdf_path_for_xlsx(protocol_xlsx_path)
    protocol_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    if cached_pdf.resolve() != protocol_pdf_path.resolve():
        shutil.copy2(cached_pdf, protocol_pdf_path)
    return protocol_pdf_path


def _protocol_display_path(protocol_path: Path) -> Path:
    if protocol_path.suffix.lower() == ".xlsx":
        return _ensure_protocol_pdf(protocol_path)
    return protocol_path


def delete_protocol_files_for_rides(
    rides: list[Pruvodka],
    *,
    scope: str = PROTOCOL_SCOPE_DAY,
    selected_date: date | None = None,
) -> int:
    if not rides and scope != PROTOCOL_SCOPE_DAY:
        return 0
    if not rides and selected_date is None:
        return 0
    tokens = protocol_filename_tokens_for_lookup(rides, scope=scope, selected_date=selected_date)
    protocol_dir = _protocol_dir()
    if not protocol_dir.exists():
        return 0
    deleted = 0
    seen: set[Path] = set()
    cache_dir = settings.MEDIA_ROOT / "print_cache" / "protokoly"
    for token in tokens:
        candidates = []
        for pattern in (
            f"protokol_{token}*.pdf",
            f"protokol_{token}*.xlsx",
            f"poznamky_{token}*.pdf",
        ):
            candidates.extend(protocol_dir.glob(pattern))
        if cache_dir.exists():
            candidates.extend(cache_dir.glob(f"protokol_{token}*.xlsx.pdf"))
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            try:
                path.unlink()
                deleted += 1
            except OSError:
                continue
    return deleted


def _latest_existing_protocol_path(
    rides: list[Pruvodka],
    *,
    scope: str = PROTOCOL_SCOPE_DAY,
    selected_date: date | None = None,
) -> Path | None:
    if not rides and scope != PROTOCOL_SCOPE_DAY:
        return None
    if not rides and selected_date is None:
        return None
    tokens = protocol_filename_tokens_for_lookup(rides, scope=scope, selected_date=selected_date)
    protocol_dir = _protocol_dir()
    if not protocol_dir.exists():
        return None
    matches: list[Path] = []
    for token in tokens:
        matches.extend(protocol_dir.glob(f"protokol_{token}*.pdf"))
    if matches:
        return max(matches, key=lambda p: p.stat().st_mtime)
    for token in tokens:
        matches.extend(protocol_dir.glob(f"protokol_{token}*.xlsx"))
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def _latest_existing_note_supplement_path(
    rides: list[Pruvodka],
    *,
    scope: str = PROTOCOL_SCOPE_DAY,
    selected_date: date | None = None,
) -> Path | None:
    if not rides:
        return None
    tokens = protocol_filename_tokens_for_lookup(rides, scope=scope, selected_date=selected_date)
    protocol_dir = _protocol_dir()
    if not protocol_dir.exists():
        return None
    matches: list[Path] = []
    for token in tokens:
        matches.extend(protocol_dir.glob(f"poznamky_{token}*.pdf"))
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def _save_protocol_note_supplement_pdf(
    rides: list[Pruvodka],
    *,
    scope: str = PROTOCOL_SCOPE_DAY,
    selected_date: date | None = None,
) -> Path | None:
    if not rides_needing_note_supplement(rides):
        return None
    payload = build_protocol_note_supplement_pdf_bytes(rides)
    if not payload:
        return None
    token = protocol_filename_token(rides, scope=scope, selected_date=selected_date)
    target_dir = _protocol_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"poznamky_{token}.pdf"
    output_path.write_bytes(payload)
    return output_path


def _protocol_label(scope: str, selected_date: date, rides: list[Pruvodka]) -> str:
    if scope == PROTOCOL_SCOPE_DAY:
        return f"Protokol jízd za den {selected_date.strftime('%d.%m.%Y')} (PDF)"
    if scope == PROTOCOL_SCOPE_GROUP and rides:
        rz = (rides[0].vehicle_rz_snapshot or "").strip() or "—"
        driver = (rides[0].driver_snapshot or "").strip() or "—"
        day = rides[0].drive_date.strftime("%d.%m.%Y") if rides[0].drive_date else selected_date.strftime("%d.%m.%Y")
        return f"Protokol jízd — RZ {rz}, řidič {driver} ({day})"
    if scope == PROTOCOL_SCOPE_SINGLE and rides:
        snd = (rides[0].snd_cislo_listu or "").strip() or f"#{rides[0].pk}"
        return f"Protokol jízdy {snd} (PDF)"
    return "Protokol jízd (PDF)"


def _append_protocol_file_row(
    file_rows: list[dict],
    protocol_path: Path,
    *,
    label: str,
    row_key: str = "",
    warning: bool = False,
) -> None:
    rel = protocol_path.relative_to(settings.MEDIA_ROOT).as_posix()
    file_rows.append(
        _file_row(
            kind="protocol",
            label=label,
            url=_media_url(rel),
            path=str(protocol_path),
            media_rel=rel,
            row_key=row_key,
            warning=warning,
        )
    )


def _append_note_supplement_file_row(
    file_rows: list[dict],
    supplement_path: Path,
    *,
    row_key: str = "",
) -> None:
    rel = supplement_path.relative_to(settings.MEDIA_ROOT).as_posix()
    file_rows.append(
        _file_row(
            kind="protocol_notes",
            label="Doplněk poznámek k protokolu (PDF)",
            url=_media_url(rel),
            path=str(supplement_path),
            media_rel=rel,
            row_key=row_key,
        )
    )


def _ensure_protocol_pdf_supplement(
    rides: list[Pruvodka],
    *,
    scope: str,
    selected_date: date | None,
) -> Path | None:
    plan_date = selected_date if scope == PROTOCOL_SCOPE_DAY else None
    existing = _latest_existing_note_supplement_path(
        rides,
        scope=scope,
        selected_date=selected_date,
    )
    if existing and not protocol_file_is_stale(rides, existing, plan_date=plan_date):
        return existing
    return _save_protocol_note_supplement_pdf(rides, scope=scope, selected_date=selected_date)


def append_protocol_and_supplement_file_rows(
    file_rows: list[dict],
    rides: list[Pruvodka],
    selected_date: date,
    *,
    scope: str = PROTOCOL_SCOPE_DAY,
    generate_if_missing: bool = False,
    force_regenerate: bool = False,
    regenerate_if_stale: bool = False,
    print_warnings: list[str] | None = None,
) -> list[dict]:
    plan_slots = []
    plan_date = None
    if scope == PROTOCOL_SCOPE_DAY:
        from waste_docs.services.reports.protocol_plan_slots import plan_only_protocol_slots

        plan_slots = plan_only_protocol_slots(selected_date)
        plan_date = selected_date

    if not rides and not plan_slots:
        return file_rows

    label = _protocol_label(scope, selected_date, rides)
    stable_protocol_key = day_protocol_row_key(selected_date) if scope == PROTOCOL_SCOPE_DAY else ""
    stable_notes_key = day_protocol_notes_row_key(selected_date) if scope == PROTOCOL_SCOPE_DAY else ""

    if (
        regenerate_if_stale
        and not force_regenerate
        and scope == PROTOCOL_SCOPE_DAY
    ):
        existing_path = _latest_existing_protocol_path(
            rides,
            scope=scope,
            selected_date=selected_date,
        )
        if existing_path is not None and protocol_file_is_stale(
            rides, existing_path, plan_date=plan_date
        ):
            force_regenerate = True

    if force_regenerate:
        delete_protocol_files_for_rides(rides, scope=scope, selected_date=selected_date)
        protocol_path = generate_protocol_xlsx(
            rides,
            scope=scope,
            selected_date=selected_date,
            print_warnings=print_warnings,
            plan_slots=plan_slots,
        )
        protocol_path = _ensure_protocol_pdf(protocol_path)
        if scope == PROTOCOL_SCOPE_DAY:
            clear_protocol_marks_for_date(selected_date)
        _append_protocol_file_row(file_rows, protocol_path, label=label, row_key=stable_protocol_key)
        supplement_path = _save_protocol_note_supplement_pdf(
            rides,
            scope=scope,
            selected_date=selected_date,
        )
        if supplement_path:
            _append_note_supplement_file_row(file_rows, supplement_path, row_key=stable_notes_key)
        return file_rows

    protocol_path = _latest_existing_protocol_path(
        rides,
        scope=scope,
        selected_date=selected_date,
    )
    if protocol_path is None and generate_if_missing:
        protocol_path = generate_protocol_xlsx(
            rides,
            scope=scope,
            selected_date=selected_date,
            print_warnings=print_warnings,
            plan_slots=plan_slots,
        )
        protocol_path = _ensure_protocol_pdf(protocol_path)
        if scope == PROTOCOL_SCOPE_DAY:
            clear_protocol_marks_for_date(selected_date)
        _save_protocol_note_supplement_pdf(rides, scope=scope, selected_date=selected_date)

    if protocol_path is None:
        return file_rows

    is_stale = protocol_file_is_stale(rides, protocol_path, plan_date=plan_date)
    display_path = _protocol_path_for_display(protocol_path)
    display_label = label
    if is_stale:
        display_label = f"{label} — zastaralý, použijte Generovat protokol"
    _append_protocol_file_row(
        file_rows,
        display_path,
        label=display_label,
        row_key=stable_protocol_key,
        warning=is_stale,
    )
    supplement_path = _latest_existing_note_supplement_path(
        rides,
        scope=scope,
        selected_date=selected_date,
    )
    if supplement_path:
        _append_note_supplement_file_row(file_rows, supplement_path, row_key=stable_notes_key)
    return file_rows


def append_day_protocol_file(
    file_rows: list[dict],
    rides: list[Pruvodka],
    selected_date: date,
    *,
    generate_if_missing: bool = False,
    force_regenerate: bool = False,
    regenerate_if_stale: bool = False,
    print_warnings: list[str] | None = None,
) -> list[dict]:
    return append_protocol_and_supplement_file_rows(
        file_rows,
        rides,
        selected_date,
        scope=PROTOCOL_SCOPE_DAY,
        generate_if_missing=generate_if_missing,
        force_regenerate=force_regenerate,
        regenerate_if_stale=regenerate_if_stale,
        print_warnings=print_warnings,
    )

