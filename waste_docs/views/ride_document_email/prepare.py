from __future__ import annotations

import json
import re
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from waste_docs.services.ride_document_email.dispatch_record import cancel_group_dispatch, record_group_dispatch
from waste_docs.services.ride_document_email.email_validate import normalize_recipient_email
from waste_docs.services.ride_document_email.recipient_presets import touch_recipient_used
from waste_docs.services.ride_document_email.eml_build import EmailAttachment, build_eml_bytes
from waste_docs.services.ride_document_email.group_attachments import build_group_email_package
from waste_docs.services.ride_document_email.permissions import user_may_email_group
from waste_docs.services.ride_document_email.subject_body import build_group_email_body, build_group_email_subject
from waste_docs.services.reports.xlsx_to_pdf import XlsxToPdfError
from waste_docs.services.ride_bulk_actions import delete_protocol_files_for_rides
from waste_docs.services.ride_protocol_xlsx import PROTOCOL_SCOPE_GROUP, rides_for_protocol_group


def _parse_date(raw: str) -> date:
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError as exc:
        raise Http404("Neplatné datum.") from exc


def _parse_vehicle_rz_id(raw: str) -> int:
    try:
        value = int((raw or "").strip())
    except (ValueError, TypeError) as exc:
        raise Http404("Neplatné RZ.") from exc
    if value <= 0:
        raise Http404("Neplatné RZ.")
    return value


def _parse_driver_id(raw: str) -> int | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except (ValueError, TypeError) as exc:
        raise Http404("Neplatný řidič skupiny.") from exc


def _parse_filter_pks(raw: str) -> list[int] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        pks = [int(p) for p in text.split(",") if p.strip().isdigit()]
    except (ValueError, TypeError) as exc:
        raise Http404("Neplatný výběr průvodek.") from exc
    return pks or None


def _parse_payload(request) -> dict:
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return request.POST


def _validate_email(raw: str) -> str:
    return normalize_recipient_email(raw)


def _safe_eml_filename(vehicle_rz: str, drive_date: date) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "_", (vehicle_rz or "").strip()).strip("_") or "skupina"
    return f"jizda_{token}_{drive_date.isoformat()}.eml"


@login_required
@require_POST
def ride_group_email_prepare(request):
    payload = _parse_payload(request)
    drive_date = _parse_date(payload.get("date") or request.POST.get("date") or "")
    vehicle_rz_id = _parse_vehicle_rz_id(
        str(payload.get("vehicle_rz_id") or request.POST.get("vehicle_rz_id") or "")
    )
    driver_id = _parse_driver_id(
        str(payload.get("driver_id") if payload.get("driver_id") is not None else request.POST.get("driver_id") or "")
    )
    filter_pks = _parse_filter_pks(
        str(payload.get("filter_pks") or payload.get("pks") or request.POST.get("filter_pks") or request.POST.get("pks") or "")
    )
    if not user_may_email_group(
        request.user,
        drive_date=drive_date,
        vehicle_rz_id=vehicle_rz_id,
        driver_id=driver_id,
        filter_pks=filter_pks,
    ):
        raise Http404("Skupina není k dispozici.")

    try:
        recipient_email = _validate_email(payload.get("recipient_email") or request.POST.get("recipient_email") or "")
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    reply_to = (getattr(request.user, "email", None) or "").strip() or None

    try:
        package = build_group_email_package(
            drive_date=drive_date,
            vehicle_rz_id=vehicle_rz_id,
            user=request.user,
            driver_id=driver_id,
            filter_pks=filter_pks,
        )
    except XlsxToPdfError as exc:
        import logging

        logging.getLogger(__name__).warning(
            "Příprava e-mailu skupiny selhala (XlsxToPdf): %s",
            exc,
        )
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)

    subject = build_group_email_subject(
        vehicle_rz=package.vehicle_rz_label,
        drive_date=drive_date,
    )
    has_protocol = package.protocol_pdf is not None
    has_merged_docs = package.pruvodky_zpo_pdf is not None
    body = build_group_email_body(
        vehicle_rz=package.vehicle_rz_label,
        drive_date=drive_date,
        ride_count=package.ride_count,
        has_merged_docs=has_merged_docs,
        has_protocol=has_protocol,
    )
    attachments: list[EmailAttachment] = []
    if package.pruvodky_zpo_pdf and package.pruvodky_zpo_filename:
        attachments.append(
            EmailAttachment(
                filename=package.pruvodky_zpo_filename,
                data=package.pruvodky_zpo_pdf,
            )
        )
    if package.protocol_pdf and package.protocol_filename:
        attachments.append(
            EmailAttachment(
                filename=package.protocol_filename,
                data=package.protocol_pdf,
            )
        )
    if not attachments:
        return JsonResponse(
            {"ok": False, "error": "Skupina nemá tisknutelné dokumenty pro e-mail."},
            status=503,
        )

    eml_bytes = build_eml_bytes(
        recipient_email=recipient_email,
        subject=subject,
        body=body,
        attachments=attachments,
        reply_to=reply_to,
    )

    protocol_rides = rides_for_protocol_group(
        drive_date,
        vehicle_rz_id,
        request.user,
        filter_pks=filter_pks,
        for_email_package=True,
        driver_id=driver_id,
    )
    if protocol_rides:
        delete_protocol_files_for_rides(
            protocol_rides,
            scope=PROTOCOL_SCOPE_GROUP,
            selected_date=drive_date,
        )

    record_group_dispatch(
        drive_date=drive_date,
        vehicle_rz_id=vehicle_rz_id,
        recipient_email=recipient_email,
        subject=subject,
        ride_count=package.ride_count,
        attachment_count=len(attachments),
        user=request.user,
    )
    touch_recipient_used(recipient_email)

    filename = _safe_eml_filename(package.vehicle_rz_label, drive_date)
    response = FileResponse(
        iter([eml_bytes]),
        content_type="message/rfc822",
        filename=filename,
    )
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@login_required
@require_POST
def ride_group_email_cancel(request):
    payload = _parse_payload(request)
    drive_date = _parse_date(payload.get("date") or request.POST.get("date") or "")
    vehicle_rz_id = _parse_vehicle_rz_id(
        str(payload.get("vehicle_rz_id") or request.POST.get("vehicle_rz_id") or "")
    )
    driver_id = _parse_driver_id(
        str(payload.get("driver_id") if payload.get("driver_id") is not None else request.POST.get("driver_id") or "")
    )
    filter_pks = _parse_filter_pks(
        str(payload.get("filter_pks") or payload.get("pks") or request.POST.get("filter_pks") or request.POST.get("pks") or "")
    )
    if not user_may_email_group(
        request.user,
        drive_date=drive_date,
        vehicle_rz_id=vehicle_rz_id,
        driver_id=driver_id,
        filter_pks=filter_pks,
    ):
        raise Http404("Skupina není k dispozici.")

    protocol_rides = rides_for_protocol_group(
        drive_date,
        vehicle_rz_id,
        request.user,
        filter_pks=filter_pks,
        for_email_package=True,
        driver_id=driver_id,
    )
    cancelled = cancel_group_dispatch(drive_date, vehicle_rz_id)
    if cancelled and protocol_rides:
        delete_protocol_files_for_rides(
            protocol_rides,
            scope=PROTOCOL_SCOPE_GROUP,
            selected_date=drive_date,
        )
    return JsonResponse({"ok": True, "cancelled": cancelled})
