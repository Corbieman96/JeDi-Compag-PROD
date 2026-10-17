from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from pypdf import PdfReader, PdfWriter

from waste_docs.models import Pruvodka
from waste_docs.services.print_bundle_prepare import prepare_print_bundle_files
from waste_docs.services.pruvodka_generated_files import (
    rides_missing_excel,
    should_generate_excel,
)
from waste_docs.services.reports.bulk_merged_print_pdf import (
    _pdf_path_for_file_row,
    filter_file_rows_for_print_kind,
)
from waste_docs.services.reports.xlsx_to_pdf import XlsxToPdfError, convert_xlsx_to_pdf
from waste_docs.services.ride_bulk_actions import build_print_rows_and_files, rides_for_print_scope
from waste_docs.services.ride_print_order import order_rides_queryset
from waste_docs.services.ride_protocol_xlsx import (
    PROTOCOL_SCOPE_GROUP,
    generate_protocol_xlsx,
    rides_for_protocol_group,
)


@dataclass(frozen=True)
class GroupEmailPackage:
    pruvodky_zpo_pdf: bytes | None
    pruvodky_zpo_filename: str | None
    protocol_pdf: bytes | None
    protocol_filename: str | None
    ride_count: int
    vehicle_rz_label: str


def _safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "_", (value or "").strip()).strip("_")
    return token or "skupina"


def _group_has_protocol_rides(rides: list[Pruvodka]) -> bool:
    return any(not getattr(ride, "is_blank_pruvodka", False) for ride in rides)


def _image_path_to_pdf(path: Path) -> Path:
    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError as exc:
        raise XlsxToPdfError(
            f"ZPO obrázek {path.name} nelze vložit do PDF (chybí PyMuPDF)."
        ) from exc
    cache_dir = settings.MEDIA_ROOT / "print_cache" / "email_dispatch"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"zpo_img_{uuid.uuid4().hex}.pdf"
    with fitz.open(path) as img_doc:
        pdf_bytes = img_doc.convert_to_pdf()
    with fitz.open("pdf", pdf_bytes) as pdf_doc:
        pdf_doc.save(out_path)
    return out_path


def _pdf_path_for_row_with_images(row: dict) -> Path:
    try:
        return _pdf_path_for_file_row(row)
    except XlsxToPdfError:
        row_kind = (row.get("kind") or "").lower()
        if row_kind != "zpo":
            raise
        raw_path = (row.get("path") or "").strip()
        if raw_path:
            path = Path(raw_path)
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                return _image_path_to_pdf(path)
        url = (row.get("url") or "").strip()
        if "/media/" in url:
            rel = url.split("/media/", 1)[1].split("?", 1)[0]
            path = (settings.MEDIA_ROOT / rel).resolve()
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                return _image_path_to_pdf(path)
        raise XlsxToPdfError(f"PDF pro ZPO není k dispozici: {row.get('label') or row_kind}")


def _merge_file_rows_to_bytes(file_rows: list[dict]) -> bytes:
    filtered = filter_file_rows_for_print_kind(file_rows, "all")
    if not filtered:
        raise XlsxToPdfError("Nebyly nalezeny soubory průvodek/ZPO pro e-mail.")
    writer = PdfWriter()
    for row in filtered:
        pdf_path = _pdf_path_for_row_with_images(row)
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            writer.add_page(page)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _reload_rides_for_email(rides: list[Pruvodka]) -> list[Pruvodka]:
    if not rides:
        return []
    return list(
        order_rides_queryset(
            Pruvodka.objects.filter(pk__in=[ride.pk for ride in rides]).select_related("activity")
        )
    )


def _email_missing_excel_message(rides: list[Pruvodka]) -> str:
    missing = rides_missing_excel(rides)
    if missing:
        labels: list[str] = []
        for ride in missing[:5]:
            snd = (ride.snd_cislo_listu or "").strip()
            labels.append(f"#{ride.pk} ({snd})" if snd else f"#{ride.pk}")
        extra = f" (+{len(missing) - 5} dalších)" if len(missing) > 5 else ""
        return f"Nepodařilo se vygenerovat Excel průvodky pro: {', '.join(labels)}{extra}."
    return (
        f"E-mail vyžaduje průvodky (Excel), ale žádné nejsou k dispozici ({len(rides)} jízd ve skupině)."
    )


def _first_attachment_filename(
    *,
    rz_token: str,
    date_token: str,
    printable: list[dict],
) -> str:
    has_xlsx = any((row.get("kind") or "").lower() == "xlsx" for row in printable)
    if has_xlsx:
        return f"pruvodky_zpo_{rz_token}_{date_token}.pdf"
    return f"zpo_{rz_token}_{date_token}.pdf"


def _email_attachments_unavailable_message(
    rides: list[Pruvodka],
    file_rows: list[dict],
    zpo_warnings: list[str],
) -> str:
    xlsx_rows = [r for r in file_rows if r.get("kind") == "xlsx" and not r.get("warning")]
    if not xlsx_rows:
        return _email_missing_excel_message(rides)
    if zpo_warnings:
        return f"E-mail vyžaduje ZPO, ale generování selhalo u: {', '.join(zpo_warnings)}."
    warning_labels = [
        (r.get("label") or r.get("kind") or "?")
        for r in file_rows
        if r.get("warning")
    ]
    if warning_labels:
        return f"Některé soubory pro e-mail nejsou k dispozici: {', '.join(warning_labels[:5])}."
    return "E-mail vyžaduje průvodky a ZPO v jednom PDF, ale tisknutelné soubory chybí."


def build_group_email_package(
    *,
    drive_date: date,
    vehicle_rz_id: int,
    user: AbstractBaseUser,
    driver_id: int | None = None,
    filter_pks: list[int] | None = None,
) -> GroupEmailPackage:
    rides = rides_for_print_scope(
        drive_date,
        user,
        vehicle_rz_id=vehicle_rz_id,
        filter_pks=filter_pks,
        for_email_package=True,
        driver_id=driver_id,
    )
    if not rides:
        raise XlsxToPdfError("Skupina neobsahuje žádné průvodky.")

    prepare_print_bundle_files(rides, include_zpo=True)
    rides = _reload_rides_for_email(rides)
    _print_rows, file_rows, zpo_warnings = build_print_rows_and_files(
        rides,
        ensure_zpo=False,
        for_email_package=True,
    )

    vehicle_rz_label = (rides[0].vehicle_rz_snapshot or "").strip() or "—"
    date_token = drive_date.isoformat()
    rz_token = _safe_token(vehicle_rz_label)

    xlsx_rows = [r for r in file_rows if r.get("kind") == "xlsx" and not r.get("warning")]
    rides_needing_excel = [ride for ride in rides if should_generate_excel(ride)]
    if rides_needing_excel and not xlsx_rows:
        raise XlsxToPdfError(_email_missing_excel_message(rides))

    printable = filter_file_rows_for_print_kind(file_rows, "all")
    if zpo_warnings and printable:
        raise XlsxToPdfError(
            f"E-mail vyžaduje ZPO, ale generování selhalo u: {', '.join(zpo_warnings)}."
        )

    pruvodky_zpo_pdf: bytes | None = None
    pruvodky_zpo_filename: str | None = None
    if printable:
        pruvodky_zpo_pdf = _merge_file_rows_to_bytes(file_rows)
        pruvodky_zpo_filename = _first_attachment_filename(
            rz_token=rz_token,
            date_token=date_token,
            printable=printable,
        )
    elif rides_needing_excel:
        raise XlsxToPdfError(
            _email_attachments_unavailable_message(rides, file_rows, zpo_warnings)
        )

    protocol_pdf: bytes | None = None
    protocol_filename: str | None = None
    if _group_has_protocol_rides(rides):
        protocol_rides = rides_for_protocol_group(
            drive_date,
            vehicle_rz_id,
            user,
            filter_pks=filter_pks,
            for_email_package=True,
            driver_id=driver_id,
        )
        if not protocol_rides:
            raise XlsxToPdfError(
                "E-mail vyžaduje protokol jízd, ale jízdy pro protokol nejsou k dispozici."
            )
        protocol_path = generate_protocol_xlsx(
            protocol_rides,
            scope=PROTOCOL_SCOPE_GROUP,
            selected_date=drive_date,
        )
        media_rel = protocol_path.relative_to(settings.MEDIA_ROOT).as_posix()
        pdf_path = convert_xlsx_to_pdf(protocol_path, media_rel=media_rel)
        protocol_pdf = pdf_path.read_bytes()
        protocol_filename = f"protokol_{rz_token}_{date_token}.pdf"

    if not pruvodky_zpo_pdf and not protocol_pdf:
        raise XlsxToPdfError("Skupina nemá tisknutelné dokumenty pro e-mail.")

    return GroupEmailPackage(
        pruvodky_zpo_pdf=pruvodky_zpo_pdf,
        pruvodky_zpo_filename=pruvodky_zpo_filename,
        protocol_pdf=protocol_pdf,
        protocol_filename=protocol_filename,
        ride_count=len(rides),
        vehicle_rz_label=vehicle_rz_label,
    )
