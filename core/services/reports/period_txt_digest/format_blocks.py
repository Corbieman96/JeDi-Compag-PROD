"""Formátování bloků TXT výcucu."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

_WEEKDAY_SHORT = ("Po", "Út", "St", "Čt", "Pá", "So", "Ne")
_NOTE_TEXT_MAX = 8000


def _weekday(d: date | None) -> str:
    if d is None:
        return ""
    return _WEEKDAY_SHORT[d.weekday()]


def _fmt_date(d: date | None) -> str:
    if d is None:
        return ""
    return f"{d.strftime('%d.%m.%Y')} ({_weekday(d)})"


def _fmt_dt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        try:
            from django.utils import timezone

            value = timezone.localtime(value)
        except Exception:
            pass
        return value.strftime("%d.%m.%Y %H:%M:%S")
    return str(value)


def _fmt_val(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "ano" if value else "ne"
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date) and not isinstance(value, datetime):
        return _fmt_date(value)
    if isinstance(value, datetime):
        return _fmt_dt(value)
    text = str(value).strip()
    return text


def _user_label(user) -> str:
    if user is None:
        return ""
    full = (getattr(user, "get_full_name", lambda: "")() or "").strip()
    uname = getattr(user, "username", "") or ""
    if full and uname:
        return f"{full} ({uname})"
    return full or uname


def _fk_label(obj, *, attr: str = "value") -> str:
    if obj is None:
        return ""
    for name in (attr, "name", "code", "rz", "title"):
        val = getattr(obj, name, None)
        if val:
            return str(val)
    return str(obj)


def _line(key: str, value) -> str:
    return f"{key}: {_fmt_val(value)}"


def format_ride_block(ride) -> list[str]:
    lines = [
        f"=== JÍZDA #{ride.pk} ===",
        _line("den", ride.drive_date),
        _line("stav", getattr(ride, "get_status_display", lambda: ride.status)()),
        _line("snd_cislo_listu", ride.snd_cislo_listu),
        _line("ride_group_number", ride.ride_group_number),
        _line("ride_sequence", ride.ride_sequence),
        _line("ride_route_order", ride.ride_route_order),
        _line("kde_adresa_snapshot", ride.address_snapshot),
        _line("kde_adresa_id", getattr(ride, "address_id", None)),
        _line("kde_adresa", _fk_label(ride.address) if getattr(ride, "address_id", None) else ""),
        _line("kdo_ridic_snapshot", ride.driver_snapshot),
        _line("kdo_ridic_id", getattr(ride, "driver_id", None)),
        _line("kdo_rz_snapshot", ride.vehicle_rz_snapshot),
        _line("kdo_rz_id", getattr(ride, "vehicle_rz_id", None)),
        _line("kdo_created_by", _user_label(ride.created_by)),
        _line("co_cinnost_snapshot", ride.activity_snapshot),
        _line("co_cinnost_id", getattr(ride, "activity_id", None)),
        _line("co_odpad_snapshot", ride.waste_type_snapshot),
        _line("co_kod_odpadu", ride.waste_code_snapshot),
        _line("co_kategorie", ride.waste_category_snapshot),
        _line("co_koncovka", ride.suffix_snapshot),
        _line("co_kontejner", ride.container_number),
        _line("co_pasport_id", getattr(ride, "container_passport_id", None)),
        _line("co_hmotnost_t", ride.weight_t),
        _line("co_hmotnost_snapshot", ride.weight_snapshot),
        _line("subjekt_snapshot", ride.name_snapshot),
        _line("subjekt_id", getattr(ride, "name_id", None)),
        _line("ico_snapshot", ride.ico_snapshot),
        _line("smlouva", ride.contract_number or ride.contract_number_snapshot),
        _line("telefon", ride.contact_phone),
        _line("poznamka", ride.contact_note),
        _line("follow_up_open", ride.follow_up_open),
        _line("follow_up_parent_id", getattr(ride, "follow_up_parent_id", None)),
        _line("follow_up_resolved_at", ride.follow_up_resolved_at),
        _line("source_waste_suffix_pair_id", getattr(ride, "source_waste_suffix_pair_id", None)),
        _line("is_blank_pruvodka", ride.is_blank_pruvodka),
        _line("is_archived", ride.is_archived),
        _line("archived_at", ride.archived_at),
        _line("archived_by", _user_label(ride.archived_by)),
        _line("archive_reason", ride.archive_reason),
        _line("created_at", ride.created_at),
        _line("updated_at", ride.updated_at),
        _line("driver_completed_at", ride.driver_completed_at),
        _line("generated_file", getattr(ride.generated_file, "name", "") or ""),
        _line("zpo_instance_file", getattr(ride.zpo_instance_file, "name", "") or ""),
        _line("zpo_instance_for_snd", ride.zpo_instance_for_snd),
    ]
    atts = list(getattr(ride, "attachments", []).all()) if hasattr(ride, "attachments") else []
    if atts:
        lines.append(_line("prilohy_pocet", len(atts)))
        for a in atts:
            lines.append(_line("priloha", getattr(a.file, "name", "") or str(a.pk)))
    lines.append("")
    return lines


def format_request_block(cr, audit_rows=None) -> list[str]:
    lines = [
        f"=== POŽADAVEK #{cr.pk} ===",
        _line("den", cr.target_date),
        _line("stav", getattr(cr, "get_status_display", lambda: cr.status)()),
        _line("kde_adresa", _fk_label(cr.address) if getattr(cr, "address_id", None) else ""),
        _line("kde_adresa_id", getattr(cr, "address_id", None)),
        _line("kde_facility_snapshot", cr.facility_address_snapshot),
        _line("kde_lat", cr.fulfillment_latitude),
        _line("kde_lng", cr.fulfillment_longitude),
        _line("kdo_subjekt", _fk_label(cr.name) if getattr(cr, "name_id", None) else ""),
        _line("kdo_subjekt_id", getattr(cr, "name_id", None)),
        _line("kdo_telefon", cr.contact_phone),
        _line("kdo_created_by", _user_label(cr.created_by)),
        _line("co_cinnost", _fk_label(cr.activity, attr="name") if getattr(cr, "activity_id", None) else ""),
        _line("co_cinnost_id", getattr(cr, "activity_id", None)),
        _line("co_druh_vozidla", _fk_label(cr.vehicle_kind, attr="name") if getattr(cr, "vehicle_kind_id", None) else ""),
        _line("co_odpad", _fk_label(cr.waste_type) if getattr(cr, "waste_type_id", None) else ""),
        _line("co_koncovka", _fk_label(cr.suffix) if getattr(cr, "suffix_id", None) else ""),
        _line("smlouva", cr.contract_number),
        _line("poznamka_do_jizdy", cr.contact_note),
        _line("poznamka_k_pozadavku", cr.note),
        _line("dispatcher_note", cr.dispatcher_note),
        _line("has_follow_up", cr.has_follow_up),
        _line(
            "follow_up_activity",
            _fk_label(cr.follow_up_activity, attr="name") if getattr(cr, "follow_up_activity_id", None) else "",
        ),
        _line("follow_up_target_date", cr.follow_up_target_date),
        _line("follow_up_parent_request_id", getattr(cr, "follow_up_parent_request_id", None)),
        _line("is_recurring", cr.is_recurring),
        _line("recurrence_weekdays", cr.recurrence_weekdays),
        _line("recurrence_until", cr.recurrence_until),
        _line("recurrence_parent_request_id", getattr(cr, "recurrence_parent_request_id", None)),
        _line("requires_advance_invoice", cr.requires_advance_invoice),
        _line("advance_invoice_amount", cr.advance_invoice_amount),
        _line("invoice_due_date", cr.invoice_due_date),
        _line("invoice_confirmed_by", _user_label(cr.invoice_confirmed_by)),
        _line("invoice_confirmed_at", cr.invoice_confirmed_at),
        _line("invoice_note", cr.invoice_note),
        _line("dispatcher_review_by", _user_label(cr.dispatcher_review_by)),
        _line("dispatcher_reviewed_at", cr.dispatcher_reviewed_at),
        _line("planned_pruvodka_id", getattr(cr, "planned_pruvodka_id", None)),
        _line("planned_follow_up_pruvodka_id", getattr(cr, "planned_follow_up_pruvodka_id", None)),
        _line("created_at", cr.created_at),
        _line("updated_at", cr.updated_at),
    ]
    atts = list(getattr(cr, "attachments", []).all()) if hasattr(cr, "attachments") else []
    if atts:
        lines.append(_line("prilohy_pocet", len(atts)))
        for a in atts:
            lines.append(_line("priloha", getattr(a.file, "name", "") or str(a.pk)))
    for log in audit_rows or []:
        lines.append(
            _line(
                "audit",
                f"{_fmt_dt(log.created_at)} | {_user_label(log.actor)} | {log.action} | {log.note}",
            )
        )
    lines.append("")
    return lines


def format_note_block(occurrence_date: date, rem, *, completions=None, exceptions=None) -> list[str]:
    text = rem.text or ""
    if len(text) > _NOTE_TEXT_MAX:
        text = text[:_NOTE_TEXT_MAX] + "\n…[zkráceno]"
    lines = [
        f"=== POZNÁMKA #{rem.pk} @ {_fmt_date(occurrence_date)} ===",
        _line("den_vyskytu", occurrence_date),
        _line("nazev", rem.title),
        _line("text", text),
        _line("kind", rem.kind),
        _line("note_group", rem.note_group),
        _line("card_color", rem.card_color),
        _line("pinned_date", rem.pinned_date),
        _line("repeat_weekdays", rem.repeat_weekdays),
        _line("repeat_monthly", rem.repeat_monthly),
        _line("repeat_active_from", rem.repeat_active_from),
        _line("repeat_active_until", rem.repeat_active_until),
        _line("rolling_start", rem.rolling_start),
        _line("snoozed_until", rem.snoozed_until),
        _line("completed_at", rem.completed_at),
        _line("created_by", _user_label(rem.created_by)),
        _line("source_svoz_task_id", getattr(rem, "source_svoz_task_id", None)),
        _line("created_at", rem.created_at),
        _line("updated_at", rem.updated_at),
    ]
    for c in completions or []:
        if c.reminder_id != rem.pk:
            continue
        lines.append(
            _line(
                "completion",
                f"{_fmt_date(c.resolved_on)} | {_fmt_dt(c.resolved_at)} | {_user_label(c.resolved_by)}",
            )
        )
    for ex in exceptions or []:
        if ex.reminder_id != rem.pk:
            continue
        lines.append(
            _line(
                "exception",
                f"z {_fmt_date(ex.original_date)} → {_fmt_date(ex.rescheduled_to)}",
            )
        )
    lines.append("")
    return lines
