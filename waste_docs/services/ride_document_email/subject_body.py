from __future__ import annotations

from datetime import date


def build_group_email_subject(
    *,
    vehicle_rz: str,
    drive_date: date,
) -> str:
    rz = (vehicle_rz or "").strip() or "—"
    return f"Průvodky a protokol — {rz} — {drive_date.strftime('%d.%m.%Y')}"


def build_group_email_body(
    *,
    vehicle_rz: str,
    drive_date: date,
    ride_count: int,
    has_merged_docs: bool,
    has_protocol: bool,
) -> str:
    rz = (vehicle_rz or "").strip() or "—"
    lines = [
        "Dobrý den,",
        "",
        f"v příloze zasíláme dokumenty ke jízdě vozidla {rz} dne {drive_date.strftime('%d.%m.%Y')}.",
        "",
        f"Počet průvodek ve skupině: {ride_count}.",
        "",
        "Přílohy:",
    ]
    attachment_no = 1
    if has_merged_docs:
        lines.append(f"{attachment_no}) Sloučený PDF soubor — průvodky a/nebo ZPO")
        attachment_no += 1
    if has_protocol:
        lines.append(f"{attachment_no}) PDF — protokol jízd")
    if not has_merged_docs and not has_protocol:
        lines.append("(Žádné přílohy.)")
    elif not has_protocol:
        lines.append("(Protokol není součástí tohoto balíčku.)")
    lines.extend(["", "S pozdravem"])
    return "\n".join(lines)
