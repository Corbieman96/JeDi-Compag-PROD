"""Po odeslání hlášení ze sběrného dvora — jednorázová poznámka pro dispečera (DayReminder)."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from catalogs.models import NameSubjectWasteSuffixPair
from day_reminders.models import DayReminder
from day_reminders.card_colors import CardColor
from waste_docs.models import SvozTask


def _pair_row_label(pair: NameSubjectWasteSuffixPair, task: SvozTask) -> str:
    label = (task.matrix_display_label or "").strip()
    if label:
        return label
    label = (pair.yard_svoz_display_label or "").strip()
    if label:
        return label
    wt = pair.waste_type
    code = (getattr(wt, "code", None) or "").strip()
    name = (getattr(wt, "value", None) or str(wt)).strip()
    if code:
        return f"{code} — {name}"
    return name


def should_create_yard_dispatch_note(pair: NameSubjectWasteSuffixPair) -> bool:
    return bool(getattr(pair, "yard_dispatch_note_enabled", False))


def build_yard_svoz_day_reminder_content(
    task: SvozTask,
    pair: NameSubjectWasteSuffixPair,
) -> tuple[str, str]:
    """Vrátí (title, text) kompatibilní s DayReminder."""
    subject = task.subject_profile
    company = (getattr(subject, "company_name", None) or str(subject)).strip()
    row_label = _pair_row_label(pair, task)

    title = (pair.yard_dispatch_note_title or "").strip()
    if not title:
        title = company
        if row_label:
            title = f"{company} · {row_label}"
    if len(title) > 160:
        title = title[:157] + "…"

    parts: list[str] = []
    template_text = (pair.yard_dispatch_note_text or "").strip()
    if template_text:
        parts.append(template_text)

    detail_lines: list[str] = []
    containers = (task.container_numbers or "").strip()
    if containers:
        detail_lines.append(f"Kontejnery: {containers}")
    yard_note = (task.yard_contact_note or "").strip()
    if yard_note:
        detail_lines.append(f"Poznámka ze dvora: {yard_note}")

    if detail_lines:
        if not template_text:
            detail_lines.insert(0, f"Subjekt: {company}")
            detail_lines.insert(1, f"Řádek matice: {row_label}")
        if parts:
            parts.append("")
        parts.extend(detail_lines)

    return title, "\n".join(parts)


def create_day_reminder_for_svoz_task(
    *,
    task: SvozTask,
    pair: NameSubjectWasteSuffixPair,
    created_by: AbstractBaseUser,
) -> DayReminder:
    title, text = build_yard_svoz_day_reminder_content(task, pair)
    return DayReminder.objects.create(
        title=title,
        text=text,
        kind=DayReminder.Kind.ONE_OFF,
        pinned_date=task.target_date,
        card_color=CardColor.RED,
        note_group=DayReminder.NoteGroup.OTHER,
        created_by=created_by,
        source_svoz_task=task,
    )


def create_unknown_passport_day_reminder(
    *,
    task: SvozTask,
    pair: NameSubjectWasteSuffixPair,
    created_by: AbstractBaseUser,
    claimed_number: str,
) -> DayReminder:
    """Poznámka dispečerovi: SD potvrdil číslo mimo číselník — jízda bez čísla, prověřit."""
    subject = task.subject_profile
    company = (getattr(subject, "company_name", None) or str(subject)).strip()
    row_label = _pair_row_label(pair, task)
    who = ""
    if created_by is not None:
        who = (getattr(created_by, "get_full_name", lambda: "")() or "").strip()
        if not who:
            who = (getattr(created_by, "username", None) or str(created_by)).strip()
    num = (claimed_number or "").strip()
    title = f"{company} · ověřit kontejner {num}"
    if len(title) > 160:
        title = title[:157] + "…"
    text = (
        f"Ze sběrného dvora ({company}) přišlo hlášení s číslem kontejneru {num}, "
        f"které není v číselníku pasportů.\n"
        f"Potvrdil: {who or 'obsluha SD'}\n"
        f"Řádek matice: {row_label}\n"
        f"Požadavek/jízda je bez čísla kontejneru — číslo prověřte a doplňte."
    )
    return DayReminder.objects.create(
        title=title,
        text=text,
        kind=DayReminder.Kind.ONE_OFF,
        pinned_date=task.target_date,
        card_color=CardColor.RED,
        note_group=DayReminder.NoteGroup.OTHER,
        created_by=created_by,
        source_svoz_task=task,
    )
