"""Tisk z detailu jízdy — průvodka a protokol (PDF)."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.urls import reverse

from core.services.ride_group_reorder import queryset_for_dashboard_ride_group
from users.services.access import can_see_all_waste_docs
from waste_docs.models import Pruvodka
from waste_docs.services.ride_print_order import order_rides_queryset
from waste_docs.services.ride_print_bundle_urls import ride_print_bundle_url


def peers_for_ride_group(ride: Pruvodka, user: User) -> list[Pruvodka]:
    qs = queryset_for_dashboard_ride_group(
        drive_date=ride.drive_date,
        vehicle_rz_id=ride.vehicle_rz_id,
        driver_id=ride.driver_id,
    )
    if not can_see_all_waste_docs(user):
        qs = qs.filter(created_by=user)
    return list(order_rides_queryset(qs.select_related("activity")))


def ride_print_bundle_url_for_ride(ride: Pruvodka) -> str:
    if not ride.drive_date or not ride.vehicle_rz_id:
        return ""
    url = ride_print_bundle_url(
        selected_date=ride.drive_date,
        vehicle_rz_id=int(ride.vehicle_rz_id),
        filter_pks=None,
        driver_id=ride.driver_id,
    )
    return url


def protocol_group_pdf_url(ride: Pruvodka) -> str:
    if not ride.drive_date or not ride.vehicle_rz_id:
        return ""
    params = (
        f"date={ride.drive_date.isoformat()}"
        f"&vehicle_rz_id={int(ride.vehicle_rz_id)}"
        f"&driver_id={int(ride.driver_id or 0)}"
    )
    return f"{reverse('waste_docs:ride_protocol_group_pdf')}?{params}"


def build_detail_print_file_rows(ride: Pruvodka, user: User) -> list[dict]:
    ctx = build_detail_print_context(ride, user)
    rows: list[dict] = []
    urls = ctx["urls"]
    if not ctx["activity_suppresses_excel"]:
        rows.append(
            {
                "kind": "pruvodka",
                "label": "Průvodka této jízdy",
                "print_url": urls["pruvodka_pdf"],
                "url": urls["pruvodka_pdf"],
                "disabled": not ctx["has_pruvodka_pdf"] and ctx.get("read_only", False),
            }
        )
    snd = (ride.snd_cislo_listu or "").strip() or f"#{ride.pk}"
    rows.append(
        {
            "kind": "protocol_single",
            "label": f"Protokol jízdy {snd}",
            "print_url": urls["protocol_single_pdf"],
            "url": urls["protocol_single_pdf"],
        }
    )
    if ctx["show_group_protocol"]:
        rz = (ride.vehicle_rz_snapshot or "").strip() or "—"
        driver = (ride.driver_snapshot or "").strip() or "—"
        rows.append(
            {
                "kind": "protocol_group",
                "label": f"Protokol skupiny — RZ {rz}, řidič {driver} ({ctx['group_peer_count']} jízd)",
                "print_url": urls["protocol_group_pdf"],
                "url": urls["protocol_group_pdf"],
            }
        )
    return rows


def build_detail_print_context(
    ride: Pruvodka,
    user: User,
    *,
    pruvodka_print_url: str = "",
    read_only: bool = False,
) -> dict:
    peers = peers_for_ride_group(ride, user)
    suppresses_excel = bool(ride.activity and ride.activity.evidence_without_excel)
    return {
        "show_group_protocol": len(peers) > 1,
        "group_peer_count": len(peers),
        "vehicle_rz_id": int(ride.vehicle_rz_id or 0),
        "driver_id": int(ride.driver_id or 0),
        "drive_date_iso": ride.drive_date.isoformat() if ride.drive_date else "",
        "ride_pk": ride.pk,
        "has_pruvodka_pdf": bool(pruvodka_print_url) or bool(ride.generated_file),
        "pruvodka_print_url": pruvodka_print_url,
        "activity_suppresses_excel": suppresses_excel,
        "read_only": read_only,
        "full_print_bundle_url": ride_print_bundle_url_for_ride(ride),
        "urls": {
            "pruvodka_pdf": reverse("waste_docs:ride_pruvodka_pdf", kwargs={"pk": ride.pk}),
            "protocol_single_pdf": reverse("waste_docs:ride_protocol_single_pdf", kwargs={"pk": ride.pk}),
            "protocol_group_pdf": protocol_group_pdf_url(ride),
            "full_print_bundle": ride_print_bundle_url_for_ride(ride),
        },
    }
