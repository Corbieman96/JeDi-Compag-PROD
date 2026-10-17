"""Sestavení UTF-8 TXT výcucu období."""

from __future__ import annotations

from datetime import date
from collections import defaultdict

from django.utils import timezone

from .format_blocks import format_note_block, format_request_block, format_ride_block
from .queries import (
    audit_logs_for_requests,
    clamp_range,
    fetch_notes_occurrences,
    fetch_requests,
    fetch_rides,
    load_note_side_data,
)


def build_period_digest_txt_bytes(
    *,
    date_from: date,
    date_to: date,
    exported_by: str = "",
) -> tuple[str, bytes]:
    """
    Vrátí (filename, utf-8 bytes).
    """
    date_from, date_to, range_truncated = clamp_range(date_from, date_to)
    rides, rides_trunc = fetch_rides(date_from, date_to)
    requests, req_trunc = fetch_requests(date_from, date_to)
    notes, notes_trunc = fetch_notes_occurrences(date_from, date_to)

    req_ids = [r.pk for r in requests]
    audits = audit_logs_for_requests(req_ids)
    audits_by_req: dict[int, list] = defaultdict(list)
    for a in audits:
        audits_by_req[a.request_id].append(a)

    rem_ids = list({rem.pk for _d, rem in notes})
    completions, exceptions = load_note_side_data(rem_ids, date_from, date_to)
    comps_by_rem: dict[int, list] = defaultdict(list)
    for c in completions:
        comps_by_rem[c.reminder_id].append(c)
    ex_by_rem: dict[int, list] = defaultdict(list)
    for ex in exceptions:
        ex_by_rem[ex.reminder_id].append(ex)

    now = timezone.localtime()
    lines: list[str] = [
        "# JeDiS — úplný TXT výcuc období (záloha)",
        f"# Období: {date_from.strftime('%d.%m.%Y')} – {date_to.strftime('%d.%m.%Y')}",
        f"# Exportováno: {now.strftime('%d.%m.%Y %H:%M:%S')}",
        f"# Uživatel: {exported_by or '—'}",
        f"# Počty: jízdy={len(rides)}, požadavky={len(requests)}, poznámky_výskyty={len(notes)}",
    ]
    if range_truncated:
        lines.append("# UPOZORNĚNÍ: období zkráceno na max. 92 dní od date_from.")
    if rides_trunc:
        lines.append("# UPOZORNĚNÍ: jízdy oříznuty na 10 000 záznamů.")
    if req_trunc:
        lines.append("# UPOZORNĚNÍ: požadavky oříznuty na 10 000 záznamů.")
    if notes_trunc:
        lines.append("# UPOZORNĚNÍ: poznámky oříznuty na 10 000 výskytů.")
    lines.extend(["", "########## JÍZDY ##########", ""])

    for ride in rides:
        lines.extend(format_ride_block(ride))

    lines.extend(["########## POŽADAVKY ##########", ""])
    for cr in requests:
        lines.extend(format_request_block(cr, audit_rows=audits_by_req.get(cr.pk, [])))

    lines.extend(["########## POZNÁMKY ##########", ""])
    for occ_day, rem in notes:
        lines.extend(
            format_note_block(
                occ_day,
                rem,
                completions=comps_by_rem.get(rem.pk, []),
                exceptions=ex_by_rem.get(rem.pk, []),
            )
        )

    body = "\n".join(lines).rstrip() + "\n"
    filename = f"jedis_vyucuc_{date_from.isoformat()}_{date_to.isoformat()}.txt"
    return filename, body.encode("utf-8")
