"""Stažení logu jednoho dvora jako .txt (chyby + odeslání)."""

from __future__ import annotations

from django.utils import timezone

from waste_docs.models.yard_svoz_submission_log import YardSvozSubmissionLog
from waste_docs.models.yard_svoz_submit_error_log import YardSvozSubmitErrorLog

from .dashboard import display_sent_row
from .query import display_row


def build_txt_bytes(*, subject_profile_id: int) -> tuple[str, bytes]:
    error_qs = (
        YardSvozSubmitErrorLog.objects.select_related(
            "subject_profile",
            "subject_profile__name",
            "created_by",
        )
        .filter(subject_profile_id=subject_profile_id)
    )
    sent_qs = (
        YardSvozSubmissionLog.objects.select_related(
            "subject_profile",
            "subject_profile__name",
            "created_by",
            "suffix",
        )
        .filter(subject_profile_id=subject_profile_id)
    )
    combined: list[tuple] = []
    subject_label = f"dvur-{subject_profile_id}"
    for entry in error_qs:
        row = display_row(entry)
        subject_label = row["subject_label"]
        kind = "prihlaseni" if row.get("source") == "login" else (
            "otevreni" if row.get("source") == "open" else (
                "kontrola" if row.get("source") == "live" else "chyba"
            )
        )
        combined.append((entry.created_at, entry.pk, kind, row))
    for entry in sent_qs:
        row = display_sent_row(entry)
        subject_label = row["subject_label"]
        combined.append((entry.submitted_at, entry.pk, "odeslano", row))
    if not combined:
        body = "Žádné záznamy v logu.\n"
        return subject_label, body.encode("utf-8")
    combined.sort(key=lambda item: (item[0], item[1] or 0))
    lines = [f"# {subject_label}", ""]
    for created_at, _pk, kind, row in combined:
        local_dt = timezone.localtime(created_at)
        parts = [
            local_dt.strftime("%Y-%m-%d %H:%M"),
            kind,
            row["created_by_label"],
        ]
        if row["display_label"]:
            parts.append(row["display_label"])
        if row["container_numbers"]:
            parts.append(f"k. {row['container_numbers']}")
        if row.get("suffix_label"):
            parts.append(f"koncovka {row['suffix_label']}")
        parts.append(row["message"])
        lines.append(" | ".join(parts))
    filename_stem = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in subject_label)[:80]
    return filename_stem or f"dvur-{subject_profile_id}", ("\n".join(lines) + "\n").encode("utf-8")
